import json
import os
import re
import sys
import difflib
import unicodedata

from app.extraction.docx_parser import extraer_docx
from app.engines.formato import revisar_formato
from app.engines.citas import procesar_citas
from app.engines.referencias import procesar_referencias
from app.engines.tablas_figuras import revisar_tablas_y_figuras
from app.engines.titulos import revisar_titulos
from reporte_pdf import generar_reporte_pdf


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFD', str(texto))
    texto_sin_tildes = ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
    return texto_sin_tildes.lower().strip()


def extraer_anio_4digitos(texto_o_anio) -> str:
    if not texto_o_anio:
        return ""
    s = str(texto_o_anio).strip().lower()
    if re.search(r's\.?\s*f\.', s):
        return "s.f."
    if re.search(r'n\.?\s*d\.', s):
        return "n.d."
    coincidencia = re.search(r'\b(19\d{2}|20\d{2})[a-z]?\b', s)
    return coincidencia.group(0) if coincidencia else ""


def obtener_texto_autor(item: dict) -> str:
    for clave in ["autor", "autores_raw", "autores", "autor_raw"]:
        val = item.get(clave)
        if val and str(val).strip():
            return str(val).strip()

    texto = item.get("texto_completo") or item.get("cita") or ""
    if texto:
        texto_sin_anio = re.sub(r'\(?\b(19\d{2}|20\d{2})\b\)?.*$', '', texto)
        texto_sin_anio = re.sub(r'[(),.:;]', ' ', texto_sin_anio)
        return texto_sin_anio.strip()

    return ""


def extraer_apellidos_clave(autor_str: str) -> set:
    """Extrae un conjunto de palabras clave de apellidos (búsqueda exacta de tokens)."""
    texto_limpio = normalizar_texto(autor_str)
    texto_limpio = re.sub(r'[^a-z\s]', ' ', texto_limpio)
    
    stopwords = {
        'y', 'e', 'o', 'v', 'et', 'al', 'amp',
        'de', 'del', 'la', 'las', 'los', 'san', 'van', 'von', 'da', 'dos'
    }
    
    tokens = texto_limpio.split()
    return {t for t in tokens if len(t) > 1 and t not in stopwords}


def primer_apellido_normalizado(autor_str: str) -> str:
    """
    Extrae el PRIMER apellido significativo respetando apellidos compuestos con guión.
    Ejemplos:
      'Fernández-Berrocal, Pablo'  → 'fernandez-berrocal'
      'Fernández, R. & Baptista'   → 'fernandez'
      'García López, M.'           → 'garcia'
    """
    texto = normalizar_texto(autor_str)
    # Limpiar cualquier signo o puntuación que preceda al apellido
    texto = re.sub(r'^[^\w]+', '', texto)
    # Eliminar partículas de nobleza al inicio
    texto = re.sub(r'^\s*(de|del|la|las|los|van|von|da|dos)\s+', '', texto)
    # Tomar el primer token (letras y guiones)
    match = re.match(r'([a-z][a-z-]*)', texto)
    return match.group(1) if match else ""


def evaluar_coincidencia(cita: dict, ref: dict) -> str:
    """
    Compara cita y referencia con matching robusto de primer apellido.
    Retorna:
    - 'EXACTA': Mismo autor y mismo año.
    - 'DISCREPANCIA_ANIO': Mismo autor pero diferente año.
    - 'NINGUNA': No coinciden en autor.

    Usa difflib.SequenceMatcher para tolerar variaciones menores (tildes, typos)
    y evita falsos positivos entre apellidos como 'Fernández-Berrocal' vs 'Fernández'.
    """
    autor_c = normalizar_texto(obtener_texto_autor(cita))
    autor_r = normalizar_texto(obtener_texto_autor(ref))

    if not autor_c or not autor_r:
        return 'NINGUNA'

    p_apellido_c = primer_apellido_normalizado(autor_c)
    p_apellido_r = primer_apellido_normalizado(autor_r)

    if not p_apellido_c or not p_apellido_r:
        return 'NINGUNA'

    # Comparación del primer apellido normalizado (sin tildes)
    if p_apellido_c != p_apellido_r:
        # Fallback: SequenceMatcher para variantes ortográficas menores
        # Umbral 0.92: acepta 'garcia'/'garsia' pero rechaza 'fernandez'/'fernandez-berrocal'
        similitud = difflib.SequenceMatcher(None, p_apellido_c, p_apellido_r).ratio()
        if similitud < 0.92:
            return 'NINGUNA'

    anio_c = extraer_anio_4digitos(cita.get("anio")) or extraer_anio_4digitos(cita.get("texto_completo"))
    anio_r = extraer_anio_4digitos(ref.get("anio")) or extraer_anio_4digitos(ref.get("texto_completo"))

    if anio_c and anio_r and anio_c == anio_r:
        return 'EXACTA'

    return 'DISCREPANCIA_ANIO'


def realizar_validacion_cruzada(citas: list, referencias: list) -> dict:
    citas_huerfanas = []
    referencias_sin_usar = []
    discrepancias_anio = []

    refs_usadas_idx = set()

    for cita in citas:
        coincidencia_hallada = False
        
        for idx, ref in enumerate(referencias):
            resultado = evaluar_coincidencia(cita, ref)
            
            if resultado == 'EXACTA':
                coincidencia_hallada = True
                refs_usadas_idx.add(idx)
                break
            elif resultado == 'DISCREPANCIA_ANIO':
                coincidencia_hallada = True
                refs_usadas_idx.add(idx)
                autor_c = obtener_texto_autor(cita)
                anio_c = extraer_anio_4digitos(cita.get("anio"))
                anio_r = extraer_anio_4digitos(ref.get("anio"))
                
                discrepancias_anio.append({
                    "autor": autor_c,
                    "anio_en_cita": anio_c,
                    "anio_en_referencia": anio_r,
                    "mensaje": f"El autor '{autor_c}' coincide, pero fue citado con el año {anio_c} y en referencias figura con {anio_r}."
                })
                break

        if not coincidencia_hallada:
            autor_c = obtener_texto_autor(cita)
            anio_c = extraer_anio_4digitos(cita.get("anio"))
            citas_huerfanas.append({
                "cita": cita.get("texto_completo") or f"{autor_c} ({anio_c})",
                "autor": autor_c,
                "anio": anio_c,
                "mensaje": f"La cita '{autor_c} ({anio_c})' aparece en el texto pero no está en las referencias."
            })

    for idx, ref in enumerate(referencias):
        if idx not in refs_usadas_idx:
            autor_r = obtener_texto_autor(ref)
            anio_r = extraer_anio_4digitos(ref.get("anio"))
            if autor_r:
                referencias_sin_usar.append({
                    "referencia": ref.get("texto_completo", ""),
                    "autor": autor_r,
                    "anio": anio_r,
                    "mensaje": f"La referencia '{autor_r} ({anio_r})' está listada pero no fue citada en el cuerpo."
                })

    return {
        "citas_huerfanas": citas_huerfanas,
        "referencias_sin_usar": referencias_sin_usar,
        "discrepancias_anio": discrepancias_anio,
        "resumen_cruce": {
            "total_citas": len(citas),
            "total_referencias": len(referencias),
            "total_citas_huerfanas": len(citas_huerfanas),
            "total_referencias_sin_usar": len(referencias_sin_usar),
            "total_discrepancias_anio": len(discrepancias_anio)
        }
    }


def ejecutar_analisis_completo(ruta_docx: str, analizar_gramatica: bool = False) -> dict:
    """
    Ejecuta el análisis APA 7 completo sobre el documento DOCX.

    Args:
        ruta_docx:          Ruta al archivo .docx a analizar.
        analizar_gramatica: Si True, ejecuta el motor de gramática (lento, requiere Java).
    """
    if not os.path.exists(ruta_docx):
        return {"error": f"El archivo '{ruta_docx}' no existe."}

    datos_doc = extraer_docx(ruta_docx)

    reporte_formato          = revisar_formato(datos_doc)
    reporte_citas            = procesar_citas(datos_doc)
    reporte_referencias      = procesar_referencias(datos_doc)
    reporte_cruce            = realizar_validacion_cruzada(reporte_citas, reporte_referencias)
    reporte_tablas_figuras   = revisar_tablas_y_figuras(datos_doc)
    reporte_titulos          = revisar_titulos(datos_doc)

    # Motor de gramática: opcional (requiere Java + language-tool-python)
    if analizar_gramatica:
        try:
            from app.engines.gramatica import revisar_gramatica, cerrar_tool
            reporte_gramatica = revisar_gramatica(datos_doc)
            cerrar_tool()
        except (ImportError, RuntimeError) as exc:
            reporte_gramatica = [{"error": str(exc)}]
    else:
        reporte_gramatica = []

    return {
        "documento": os.path.basename(ruta_docx),
        "gramatica_activada": analizar_gramatica,
        "formato": reporte_formato,
        "citas": {
            "lista": reporte_citas,
            "total_detectadas": len(reporte_citas)
        },
        "referencias": {
            "lista": reporte_referencias,
            "total_detectadas": len(reporte_referencias)
        },
        "tablas_y_figuras": reporte_tablas_figuras,
        "cruce_citas_referencias": reporte_cruce,
        "titulos": {
            "lista": reporte_titulos,
            "total_hallazgos": len(reporte_titulos)
        },
        "gramatica": {
            "lista": reporte_gramatica,
            "total_errores": len(reporte_gramatica)
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verificador de normas APA 7 para documentos .docx"
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        default="tests/Trabajo de Investigación - Isabel - Junior.docx",
        help="Ruta al archivo .docx a analizar."
    )
    parser.add_argument(
        "--gramatica",
        action="store_true",
        default=False,
        help=(
            "Activa el análisis ortográfico y gramatical con LanguageTool "
            "(requiere Java 8+ y 'pip install language-tool-python')."
        ),
    )
    parser.add_argument(
        "--pdf",
        default="reporte_diagnostico_apa.pdf",
        help="Nombre del archivo PDF de salida (default: reporte_diagnostico_apa.pdf).",
    )
    args = parser.parse_args()

    reporte = ejecutar_analisis_completo(args.ruta, analizar_gramatica=args.gramatica)

    # 1. Imprime la estructura JSON en la consola
    print(json.dumps(reporte, indent=2, ensure_ascii=False))

    # 2. Genera el PDF con los resultados
    generar_reporte_pdf(reporte, args.pdf)