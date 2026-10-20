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



def es_referencia(parrafo):
    # Firma de sangría francesa: primera línea negativa
    return (
        parrafo["sangria_primera_linea_cm"] is not None
        and parrafo["sangria_primera_linea_cm"] < 0
    )


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
        if abs(valor - REGLAS["margen_cm"]) > TOLERANCIA_CM:
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
    fuente = parrafo["fuente"]
    tamano = parrafo["tamano_fuente_pt"]

    if fuente is None and tamano is None:
        return []

    # Evaluar si la combinación fuente+tamaño es aceptada por APA 7
    combinacion_valida = False
    for fuente_ok, tamano_ok in COMBINACIONES_FUENTE_ACEPTADAS:
        fuente_coincide = (fuente is None) or (fuente == fuente_ok)
        tamano_coincide = (tamano is None) or (tamano == tamano_ok)
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
    if parrafo["interlineado"] is None:
        return []

    if parrafo["interlineado"] != REGLAS["interlineado"]:
        return [{
            "tipo": "interlineado",
            "mensaje": f"Interlineado {parrafo['interlineado']}, se espera {REGLAS['interlineado']}",
            "valor_encontrado": parrafo["interlineado"],
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
        primera = parrafo["sangria_primera_linea_cm"]
        izquierda = parrafo["sangria_izquierda_cm"]
        if primera is None or abs(primera - REGLAS["sangria_primera_linea_referencia"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "sangria",
                "mensaje": f"Sangría francesa (primera línea) de {primera}cm, se espera {REGLAS['sangria_primera_linea_referencia']}cm",
                "valor_encontrado": primera,
                "valor_esperado": REGLAS["sangria_primera_linea_referencia"],
                "parrafo": texto_corto,
            })
        if izquierda is None or abs(izquierda - REGLAS["sangria_izquierda_referencia"]) > TOLERANCIA_CM:
            hallazgos.append({
                "tipo": "sangria",
                "mensaje": f"Sangría francesa (izquierda) de {izquierda}cm, se espera {REGLAS['sangria_izquierda_referencia']}cm",
                "valor_encontrado": izquierda,
                "valor_esperado": REGLAS["sangria_izquierda_referencia"],
                "parrafo": texto_corto,
            })
    else:
        primera = parrafo["sangria_primera_linea_cm"]
        if primera is None or abs(primera - REGLAS["sangria_primera_linea_cuerpo"]) > TOLERANCIA_CM:
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