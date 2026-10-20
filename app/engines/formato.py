import re

# --- Reglas base APA7 / UNFV ---
REGLAS = {
    "fuente": "Arial",
    "tamano_fuente": 12.0,
    "interlineado": 2.0,
    "alineacion_cuerpo": "JUSTIFY",
    "sangria_primera_linea_cuerpo": 1.27,
    "sangria_primera_linea_referencia": -1.27,
    "sangria_izquierda_referencia": 1.27,
    "margen_cm": 2.54,
}

# Combinaciones fuente/tamaño aceptadas por APA 7 (capítulo 2) y directrices UNFV
COMBINACIONES_FUENTE_ACEPTADAS = [
    ("Arial", 12.0),
    ("Arial", 11.0),
    ("Times New Roman", 12.0),
    ("Times New Roman", 11.0),
    ("Calibri", 11.0),
    ("Georgia", 11.0),
    ("Computer Modern", 10.0),
]

TOLERANCIA_CM = 0.05  # margen de error por redondeos de Word/python-docx


def safe_int(val, default=0):
    """Convierte de forma segura cualquier valor (incluyendo cadenas flotantes) a entero."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    """Convierte de forma segura cualquier valor a float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def es_referencia(parrafo):
    # Firma de sangría francesa: primera línea negativa
    primera = parrafo.get("sangria_primera_linea_cm")
    if primera is None:
        return False
    try:
        return safe_float(primera) < 0
    except (ValueError, TypeError):
        return False


def es_titulo_o_subtitulo(parrafo):
    texto = parrafo["texto"].strip()
    if not texto:
        return False

    # 0. Estilo de encabezado Word si está presente
    estilo = (parrafo.get("estilo") or "").lower()
    if any(h in estilo for h in ["heading", "título", "titulo", "encabezado"]):
        return True

    # 1. Títulos centrados (Ej: Dedicatoria, Resumen, Nivel 1 APA)
    if parrafo["alineacion"] == "CENTER":
        return True

    # 2. Etiquetas de Tabla o Figura (Ej: "Tabla 1", "Figura 2")
    if re.match(r'^(Tabla|Figura)\s+\d+', texto, re.IGNORECASE):
        return True

    # 3. Subtítulos (numerados o no) y títulos de tablas:
    # Suelen ser textos relativamente cortos (< 100 caracteres) y no terminan en punto final
    if len(texto) < 100 and not texto.endswith('.'):
        return True

    return False


def revisar_margenes(margenes):
    hallazgos = []
    for lado, valor in margenes.items():
        if valor is None:
            continue
        try:
            val_num = safe_float(valor)
        except Exception:
            continue
        if abs(val_num - REGLAS["margen_cm"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "margenes",
                "mensaje": f"Margen {lado} de {valor}cm, se espera {REGLAS['margen_cm']}cm",
                "valor_encontrado": valor,
                "valor_esperado": REGLAS["margen_cm"],
            })
    return hallazgos


def revisar_fuente(parrafo):
    hallazgos = []
    texto_corto = parrafo["texto"][:60]
    fuente = parrafo.get("fuente")
    tamano_raw = parrafo.get("tamano_fuente_pt")
    tamano = safe_float(tamano_raw, default=None) if tamano_raw is not None else None

    if fuente is None and tamano is None:
        return []

    # Evaluar si la combinación fuente+tamaño es aceptada por APA 7
    combinacion_valida = False
    for fuente_ok, tamano_ok in COMBINACIONES_FUENTE_ACEPTADAS:
        fuente_coincide = (fuente is None) or (fuente == fuente_ok)
        tamano_coincide = (tamano is None) or (abs(tamano - tamano_ok) < 0.1)
        if fuente_coincide and tamano_coincide:
            combinacion_valida = True
            break

    if not combinacion_valida:
        # Reportar solo si hay datos concretos (evitar ruido cuando ambos son None)
        if fuente is not None and tamano is not None:
            hallazgos.append({
                "tipo": "fuente",
                "mensaje": (
                    f"Fuente '{fuente}' {tamano}pt no está entre las aceptadas por APA 7. "
                    f"Use: Arial 12pt, Arial 11pt, Times New Roman 12pt, Calibri 11pt, Georgia 11pt."
                ),
                "valor_encontrado": f"{fuente} {tamano}pt",
                "valor_esperado": "Arial 12pt / Times New Roman 12pt / Arial 11pt",
                "parrafo": texto_corto,
            })
        elif fuente is not None:
            fuentes_aceptadas = {f for f, _ in COMBINACIONES_FUENTE_ACEPTADAS}
            if fuente not in fuentes_aceptadas:
                hallazgos.append({
                    "tipo": "fuente",
                    "mensaje": f"Fuente '{fuente}' no es una de las aceptadas por APA 7.",
                    "valor_encontrado": fuente,
                    "valor_esperado": "Arial / Times New Roman / Calibri / Georgia",
                    "parrafo": texto_corto,
                })

    return hallazgos


def revisar_interlineado(parrafo):
    inter = parrafo.get("interlineado")
    if inter is None:
        return []

    es_valido = False
    try:
        if isinstance(inter, (int, float)):
            es_valido = abs(safe_float(inter) - REGLAS["interlineado"]) < 0.05
        elif isinstance(inter, str):
            inter_limpio = inter.replace("pt", "").strip()
            val_num = safe_float(inter_limpio)
            if "pt" in inter:
                tamano_fuente = safe_float(parrafo.get("tamano_fuente_pt"), 12.0)
                es_valido = abs(val_num - (tamano_fuente * REGLAS["interlineado"])) < 1.0
            else:
                es_valido = abs(val_num - REGLAS["interlineado"]) < 0.05
    except (ValueError, TypeError):
        es_valido = (inter == REGLAS["interlineado"])

    if not es_valido:
        return [{
            "tipo": "interlineado",
            "mensaje": f"Interlineado {inter}, se espera {REGLAS['interlineado']}",
            "valor_encontrado": inter,
            "valor_esperado": REGLAS["interlineado"],
            "parrafo": parrafo["texto"][:60],
        }]
    return []


def revisar_alineacion_y_sangria(parrafo):
    if es_titulo_o_subtitulo(parrafo):
        return []

    hallazgos = []
    texto_corto = parrafo["texto"][:60]

    if parrafo["alineacion"] != REGLAS["alineacion_cuerpo"]:
        hallazgos.append({
            "tipo": "alineacion",
            "mensaje": f"Alineación '{parrafo['alineacion']}', se espera '{REGLAS['alineacion_cuerpo']}'",
            "valor_encontrado": parrafo["alineacion"],
            "valor_esperado": REGLAS["alineacion_cuerpo"],
            "parrafo": texto_corto,
        })

    if es_referencia(parrafo):
        primera = parrafo.get("sangria_primera_linea_cm")
        izquierda = parrafo.get("sangria_izquierda_cm")
        primera_val = safe_float(primera, default=None) if primera is not None else None
        izquierda_val = safe_float(izquierda, default=None) if izquierda is not None else None

        if primera_val is None or abs(primera_val - REGLAS["sangria_primera_linea_referencia"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "sangria",
                "mensaje": f"Sangría francesa (primera línea) de {primera}cm, se espera {REGLAS['sangria_primera_linea_referencia']}cm",
                "valor_encontrado": primera,
                "valor_esperado": REGLAS["sangria_primera_linea_referencia"],
                "parrafo": texto_corto,
            })
        if izquierda_val is None or abs(izquierda_val - REGLAS["sangria_izquierda_referencia"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "sangria",
                "mensaje": f"Sangría francesa (izquierda) de {izquierda}cm, se espera {REGLAS['sangria_izquierda_referencia']}cm",
                "valor_encontrado": izquierda,
                "valor_esperado": REGLAS["sangria_izquierda_referencia"],
                "parrafo": texto_corto,
            })
    else:
        primera = parrafo.get("sangria_primera_linea_cm")
        primera_val = safe_float(primera, default=None) if primera is not None else None
        if primera_val is None or abs(primera_val - REGLAS["sangria_primera_linea_cuerpo"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "sangria",
                "mensaje": f"Sangría de primera línea {primera}cm, se espera {REGLAS['sangria_primera_linea_cuerpo']}cm",
                "valor_encontrado": primera,
                "valor_esperado": REGLAS["sangria_primera_linea_cuerpo"],
                "parrafo": texto_corto,
            })

    return hallazgos


def revisar_formato(datos_extraidos):
    hallazgos = []
    hallazgos.extend(revisar_margenes(datos_extraidos["margenes"]))

    for parrafo in datos_extraidos["parrafos"]:
        if parrafo.get("en_tabla"):
            continue  # El texto dentro de celdas de tablas no sigue las reglas de sangría del cuerpo en APA 7
        en_portada = parrafo.get("en_portada", False)
        hallazgos.extend(revisar_fuente(parrafo))
        if not en_portada:
            # Las reglas de interlineado doble y sangría NO aplican a la portada/carátula
            hallazgos.extend(revisar_interlineado(parrafo))
            hallazgos.extend(revisar_alineacion_y_sangria(parrafo))


    return hallazgos


if __name__ == "__main__":
    import json
    import os
    import sys

    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(directorio_actual, "..", "extraction"))
    from docx_parser import extraer_docx

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    datos = extraer_docx(ruta)
    hallazgos = revisar_formato(datos)
    print(json.dumps(hallazgos, indent=2, ensure_ascii=False))