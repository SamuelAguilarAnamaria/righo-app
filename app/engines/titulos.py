import re
import unicodedata


# ---------------------------------------------------------------------------
# Reglas de formato por nivel APA 7 (Tabla 2.1 del manual)
# ---------------------------------------------------------------------------
# Nivel | Centrado | Negrita | Cursiva | Sangría | Termina en punto
#   1   |    Sí    |   Sí    |   No    |   No    |       No
#   2   |    No    |   Sí    |   No    |   No    |       No
#   3   |    No    |   Sí    |   Sí    |   No    |       No
#   4   |    No    |   Sí    |   No    |   Sí    |       Sí
#   5   |    No    |   Sí    |   Sí    |   Sí    |       Sí
REGLAS_NIVEL: dict[int, dict] = {
    1: {"centrado": True,  "negrita": True,  "cursiva": False, "sangria": False, "punto_final": False},
    2: {"centrado": False, "negrita": True,  "cursiva": False, "sangria": False, "punto_final": False},
    3: {"centrado": False, "negrita": True,  "cursiva": True,  "sangria": False, "punto_final": False},
    4: {"centrado": False, "negrita": True,  "cursiva": False, "sangria": True,  "punto_final": True},
    5: {"centrado": False, "negrita": True,  "cursiva": True,  "sangria": True,  "punto_final": True},
}

# Mapeo de nombres de estilo Word → nivel APA
MAPEO_ESTILOS: dict[str, int] = {
    "heading 1": 1, "título 1": 1, "encabezado 1": 1,
    "heading 2": 2, "título 2": 2, "encabezado 2": 2,
    "heading 3": 3, "título 3": 3, "encabezado 3": 3,
    "heading 4": 4, "título 4": 4, "encabezado 4": 4,
    "heading 5": 5, "título 5": 5, "encabezado 5": 5,
}

# Umbral de sangría (cm) para considerar que un párrafo tiene sangría
UMBRAL_SANGRIA_CM = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Elimina tildes y pasa a minúsculas para comparaciones robustas."""
    nfd = unicodedata.normalize('NFD', texto)
    sin_tildes = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return sin_tildes.lower().strip()


def _detectar_nivel_desde_estilo(nombre_estilo: str) -> int | None:
    """Retorna el nivel APA (1-5) a partir del nombre de estilo Word, o None si no es encabezado."""
    if not nombre_estilo:
        return None
    return MAPEO_ESTILOS.get(_normalizar(nombre_estilo))


def _es_title_case(texto: str) -> bool:
    """
    Verifica capitalización Title Case flexible:
    - Al menos la primera palabra debe estar capitalizada.
    - Las palabras funcionales cortas (art., prep., conj.) pueden ir en minúsculas.
    """
    PALABRAS_FUNCIONALES = {
        'a', 'al', 'de', 'del', 'el', 'en', 'es', 'la', 'las', 'lo',
        'los', 'o', 'para', 'por', 'que', 'un', 'una', 'y', 'e',
        'con', 'sin', 'sobre', 'ante', 'bajo', 'como',
    }
    palabras = texto.split()
    if not palabras:
        return True
    # La primera palabra siempre debe estar capitalizada
    if not palabras[0][0].isupper():
        return False
    # El resto: si no es funcional y tiene más de 1 char, debe estar capitalizada
    for palabra in palabras[1:]:
        limpia = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]', '', palabra)
        if limpia and limpia.lower() not in PALABRAS_FUNCIONALES:
            if limpia[0].islower():
                return False
    return True


def _inferir_formato_parrafo(p: dict) -> dict:
    """
    Infiere si el párrafo tiene negrita y cursiva a partir de los datos del parser.
    Nota: docx_parser.py actualmente no extrae es_negrita/es_cursiva para párrafos normales;
    se usa heurística de estilo (Heading) como proxy principal.
    """
    # La info de negrita/cursiva sería ideal, pero el parser actual la extrae solo para tablas.
    # Se deja como estructura para futura extensión.
    return {
        "negrita": None,   # No disponible en parser actual para párrafos normales
        "cursiva": None,
    }


# ---------------------------------------------------------------------------
# Validador principal
# ---------------------------------------------------------------------------

def _validar_titulo(p: dict, nivel: int) -> list[dict]:
    """
    Valida un párrafo de encabezado contra las reglas APA 7 del nivel dado.
    Retorna lista de hallazgos (puede estar vacía si todo es correcto).
    """
    regla = REGLAS_NIVEL[nivel]
    texto = p.get("texto", "").strip()
    hallazgos = []

    # --- Alineación ---
    alineacion_actual = p.get("alineacion")
    if regla["centrado"]:
        if alineacion_actual not in ("CENTER", "DISTRIBUTE"):
            hallazgos.append({
                "tipo": "titulo_alineacion",
                "mensaje": f"Nivel {nivel}: debe estar centrado (actual: '{alineacion_actual}').",
                "valor_encontrado": alineacion_actual,
                "valor_esperado": "CENTER",
            })
    else:
        if alineacion_actual not in ("LEFT", "JUSTIFY", None):
            hallazgos.append({
                "tipo": "titulo_alineacion",
                "mensaje": f"Nivel {nivel}: debe estar alineado a la izquierda (actual: '{alineacion_actual}').",
                "valor_encontrado": alineacion_actual,
                "valor_esperado": "LEFT",
            })

    # --- Sangría ---
    sangria_cm = p.get("sangria_primera_linea_cm")
    tiene_sangria = sangria_cm is not None and sangria_cm >= UMBRAL_SANGRIA_CM
    if regla["sangria"] and not tiene_sangria:
        hallazgos.append({
            "tipo": "titulo_sangria",
            "mensaje": f"Nivel {nivel}: requiere sangría de primera línea (≥ 1.27 cm). Actual: {sangria_cm} cm.",
            "valor_encontrado": sangria_cm,
            "valor_esperado": 1.27,
        })
    elif not regla["sangria"] and tiene_sangria:
        hallazgos.append({
            "tipo": "titulo_sangria",
            "mensaje": f"Nivel {nivel}: NO debe tener sangría de primera línea. Actual: {sangria_cm} cm.",
            "valor_encontrado": sangria_cm,
            "valor_esperado": 0,
        })

    # --- Punto final (niveles 4 y 5) ---
    if regla["punto_final"] and not texto.endswith('.'):
        hallazgos.append({
            "tipo": "titulo_falta_punto",
            "mensaje": f"Nivel {nivel}: el encabezado debe terminar con punto.",
            "valor_encontrado": texto[-10:] if len(texto) > 10 else texto,
            "valor_esperado": "...",
        })
    elif not regla["punto_final"] and texto.endswith('.'):
        hallazgos.append({
            "tipo": "titulo_punto_sobrante",
            "mensaje": f"Nivel {nivel}: el encabezado NO debe terminar con punto.",
            "valor_encontrado": texto[-10:] if len(texto) > 10 else texto,
            "valor_esperado": "sin punto",
        })

    # --- Title Case ---
    if not _es_title_case(texto):
        hallazgos.append({
            "tipo": "titulo_capitalizacion",
            "mensaje": f"Nivel {nivel}: el texto no cumple el formato Title Case de APA 7.",
            "valor_encontrado": texto[:60],
            "valor_esperado": "Title Case",
        })

    return hallazgos


def _detectar_nivel_regex(texto: str) -> int | None:
    """
    Fallback: infiere el nivel APA de un título a partir de patrones de numeración
    en el texto. Aplica solo cuando el documento no usa estilos nativos de Word.
    Ejemplos detectados:
      '1 Introducción'       → nivel 1
      '1.1 Marco Teórico'    → nivel 2
      '1.1.1 Sub-sección'    → nivel 3
    """
    # Numeración jerárquica explícita (1, 1.1, 1.1.1, etc.)
    m = re.match(r'^(\d+(?:\.\d+)*)\s+\S', texto.strip())
    if m:
        profundidad = m.group(1).count('.') + 1  # "1" → 1, "1.1" → 2
        return min(profundidad, 5)
    return None


def _tiene_negrita_todos_runs(p_dict: dict) -> bool:
    """
    Retorna True si el párrafo tiene el campo 'es_negrita' marcado,
    o si el estilo es Heading (proxy cuando el parser no extrae negrita explícita).
    """
    if p_dict.get("es_negrita") is True:
        return True
    estilo = (p_dict.get("estilo") or "").lower()
    return any(h in estilo for h in ["heading", "título", "titulo", "encabezado"])


def revisar_titulos(datos_extraidos: dict) -> list[dict]:
    """
    Audita la jerarquía de títulos (Niveles 1-5) de un documento APA 7.

    Estrategia en dos fases:
    1. Detección primaria: estilos nativos Word (Heading 1-5).
    2. Fallback: párrafos en negrita con numeración jerárquica (regex) cuando
       el documento no usa estilos nativos y se devolvería 0 títulos.

    Retorna lista de dicts con:
      - texto: texto del encabezado
      - nivel: nivel APA detectado (1-5)
      - errores: lista de hallazgos de formato
    """
    resultados = []

    for p in datos_extraidos.get("parrafos", []):
        if p.get("en_tabla"):
            continue

        estilo = p.get("estilo", "") or ""
        nivel = _detectar_nivel_desde_estilo(estilo)

        if nivel is None:
            continue  # No es un encabezado según su estilo Word

        texto = p.get("texto", "").strip()
        if not texto:
            continue

        hallazgos = _validar_titulo(p, nivel)

        resultados.append({
            "texto": texto,
            "nivel": nivel,
            "estilo_word": estilo,
            "errores": hallazgos,
            "metodo_deteccion": "estilo_word",
        })

    # --- Fallback: si no se encontraron títulos por estilo, buscar por regex+negrita ---
    if not resultados:
        for p in datos_extraidos.get("parrafos", []):
            if p.get("en_tabla"):
                continue

            texto = p.get("texto", "").strip()
            if not texto:
                continue

            # Solo párrafos que parecen títulos (negrita o estilo heading)
            if not _tiene_negrita_todos_runs(p):
                continue

            nivel = _detectar_nivel_regex(texto)
            if nivel is None:
                continue

            hallazgos = _validar_titulo(p, nivel)

            resultados.append({
                "texto": texto,
                "nivel": nivel,
                "estilo_word": p.get("estilo", ""),
                "errores": hallazgos,
                "metodo_deteccion": "fallback_regex",
            })

    return resultados



if __name__ == "__main__":
    import json
    import os
    import sys

    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(directorio_actual, "..", "extraction"))
    from docx_parser import extraer_docx

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    datos = extraer_docx(ruta)
    resultado = revisar_titulos(datos)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
