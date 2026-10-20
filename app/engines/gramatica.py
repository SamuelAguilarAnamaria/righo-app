"""
Módulo de revisión ortográfica y gramatical usando LanguageTool.
Soporta detección automática de idioma (incluyendo español e inglés).

Requiere:
    pip install language-tool-python
    Java 8+ instalado en el sistema.

Activación: opcional, controlada por el flag --gramatica en la CLI.
El servidor LanguageTool se descarga (~200 MB) en el primer uso.
"""
from __future__ import annotations

import re

# Singleton lazy-initialized para evitar múltiples instancias del servidor JVM
_tool = None


def _get_tool():
    """Inicializa y retorna el singleton de LanguageTool forzado a español peruano (es-PE)."""
    global _tool
    if _tool is None:
        try:
            import language_tool_python  # type: ignore
            # Forzar español para evitar que LanguageTool use diccionarios en inglés/alemán
            # y marque palabras en español como errores (ej. ESCUELA → RESCUE).
            try:
                _tool = language_tool_python.LanguageTool('es-PE')
            except Exception:
                # Fallback a español genérico si es-PE no está disponible
                _tool = language_tool_python.LanguageTool('es')
        except ImportError:
            raise ImportError(
                "El paquete 'language-tool-python' no está instalado.\n"
                "Instálalo con: pip install language-tool-python\n"
                "También necesitas Java 8+ en tu sistema."
            )
        except Exception as exc:
            raise RuntimeError(
                f"No se pudo inicializar LanguageTool: {exc}\n"
                "Verifica que Java 8+ esté instalado y accesible en el PATH."
            ) from exc
    return _tool



# IDs de reglas de LanguageTool que generan demasiado ruido en textos académicos
REGLAS_EXCLUIDAS: set[str] = {
    "WHITESPACE_RULE",
    "COMMA_PARENTHESIS_WHITESPACE",
    "DOUBLE_PUNCTUATION",
    "UNPAIRED_BRACKETS",
    # Reglas de puntuación que chocan con citas APA
    "ES_QUESTION_MARK",
    "ES_EXCLAMATION_MARK",
}


def _es_parrafo_omitible(texto: str) -> bool:
    """
    Retorna True si el párrafo debe ser omitido del análisis gramatical:
    - Textos muy cortos (probablemente títulos o etiquetas)
    - Texto completamente en MAYÚSCULAS (portadas, carátulas, encabezados institucionales)
    - Alta proporción de palabras en mayúsculas (nombre de instituciones, siglas)
    - URLs o DOIs
    - Referencias bibliográficas (comienzan con patrón Apellido, I.)
    - Números solos (tablas de datos)
    """
    t = texto.strip()
    if len(t) < 40:
        return True
    # Omitir párrafos completamente en MAYÚSCULAS (portada, carátulas, encabezados)
    palabras = t.split()
    if t.isupper():
        return True
    # Omitir si más del 60% de las palabras (≥2 chars) están en mayúsculas (siglas/instituciones)
    palabras_content = [p for p in palabras if len(p) >= 2]
    if palabras_content:
        mayusculas_count = sum(1 for p in palabras_content if p.isupper())
        if mayusculas_count / len(palabras_content) > 0.6:
            return True
    if re.match(r'^https?://', t):
        return True
    if re.match(r'^doi\.org/', t, re.IGNORECASE):
        return True
    # Patrón de referencia bibliográfica: "Apellido, X. (YYYY)"
    if re.match(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+[,\s].{0,30}\(\d{4}', t):
        return True
    # Solo números y signos (fila de tabla de datos)
    if re.match(r'^[\d\s.,;%()+-]+$', t):
        return True
    return False




def revisar_gramatica(
    datos_extraidos: dict,
    max_parrafos: int = 50,
) -> list[dict]:
    """
    Analiza ortografía y gramática del cuerpo del documento.

    Args:
        datos_extraidos: Dict retornado por docx_parser.extraer_docx().
        max_parrafos:    Número máximo de párrafos a analizar (para controlar tiempo).

    Returns:
        Lista de dicts con los errores encontrados. Cada dict contiene:
        - parrafo_extracto: primeros 80 caracteres del párrafo
        - offset:          posición del error en el texto
        - mensaje:         descripción del error (en español)
        - sugerencias:     lista de correcciones sugeridas (máx. 3)
        - regla_id:        ID de la regla LanguageTool que disparó el error
        - categoria:       categoría del error (TYPOS, GRAMMAR, STYLE, etc.)
    """
    tool = _get_tool()
    errores_encontrados: list[dict] = []
    parrafos_analizados = 0
    en_referencias = False

    for p in datos_extraidos.get("parrafos", []):
        texto = p.get("texto", "").strip() if isinstance(p, dict) else str(p).strip()

        # Detener análisis al llegar a la sección de referencias
        if re.match(
            r'^\s*(REFERENCIAS|REFERENCIAS BIBLIOGRÁFICAS|BIBLIOGRAFÍA|REFERENCES|WORKS CITED)\s*$',
            texto, re.IGNORECASE
        ):
            en_referencias = True

        if en_referencias:
            continue

        if _es_parrafo_omitible(texto):
            continue

        try:
            matches = tool.check(texto)
        except Exception:
            continue  # Ignorar errores del servidor en un párrafo específico

        for match in matches:
            # Filtrar reglas excluidas
            rule_id = getattr(match, "rule_id", getattr(match, "ruleId", ""))
            if rule_id in REGLAS_EXCLUIDAS:
                continue

            error_len = getattr(match, "error_length", getattr(match, "errorLength", 0))

            errores_encontrados.append({
                "parrafo_extracto": texto[:80] + ("..." if len(texto) > 80 else ""),
                "offset": match.offset,
                "fragmento_error": texto[match.offset: match.offset + error_len],
                "mensaje": match.message,
                "sugerencias": list(match.replacements[:3]),
                "regla_id": rule_id,
                "categoria": str(getattr(match, "category", "UNKNOWN")),
            })

        parrafos_analizados += 1
        if parrafos_analizados >= max_parrafos:
            break

    return errores_encontrados


def cerrar_tool():
    """Cierra el servidor LanguageTool (libera el proceso Java)."""
    global _tool
    if _tool is not None:
        try:
            _tool.close()
        except Exception:
            pass
        finally:
            _tool = None


if __name__ == "__main__":
    import json
    import os
    import sys

    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(directorio_actual, "..", "extraction"))
    from docx_parser import extraer_docx

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    datos = extraer_docx(ruta)
    resultado = revisar_gramatica(datos)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    cerrar_tool()