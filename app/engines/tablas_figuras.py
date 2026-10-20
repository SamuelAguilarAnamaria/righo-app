import re


def validar_nota_apa7(texto_nota: str) -> list:
    """Valida la sintaxis de la nota al pie de tabla/figura."""
    errores = []
    texto_l = texto_nota.strip()

    if not texto_l.startswith("Nota.") and not texto_l.startswith("Nota:"):
        if re.match(r'^nota\b', texto_l, re.IGNORECASE):
            errores.append({
                "tipo": "nota_formato_incorrecto",
                "mensaje": "La nota debe iniciar exactamente con 'Nota.' en cursiva."
            })
    return errores


def revisar_tablas_y_figuras(datos_doc: dict) -> dict:
    """
    Audita tablas y figuras bajo los lineamientos de APA 7.
    """
    reporte_tablas = []
    reporte_figuras = []

    # 1. Auditoría de Tablas
    tablas = datos_doc.get("tablas", [])
    for idx, tbl in enumerate(tablas, start=1):
        hallazgos = []
        num_texto = tbl.get("numero_texto", "")
        titulo_texto = tbl.get("titulo_texto", "")
        nota_texto = tbl.get("nota_texto", "")
        tiene_lineas_verticales = tbl.get("lineas_verticales", False)

        # Regla 1: Formato del Número ("Tabla X" en negrita)
        if not tbl.get("numero_es_negrita", False):
            hallazgos.append({
                "tipo": "tabla_numero_sin_negrita",
                "mensaje": f"El etiqueta '{num_texto}' debe estar completamente en negrita."
            })

        # Regla 2: Formato del Título (en cursiva)
        if not tbl.get("titulo_es_cursiva", False):
            hallazgos.append({
                "tipo": "tabla_titulo_sin_cursiva",
                "mensaje": f"El título de la tabla ('{titulo_texto}') debe estar en cursiva."
            })

        # Regla 3: Bordes en APA 7
        if tiene_lineas_verticales:
            hallazgos.append({
                "tipo": "tabla_lineas_verticales",
                "mensaje": "APA 7 no permite bordes verticales en las tablas. Utiliza solo bordes horizontales."
            })

        # Regla 4: Validar Nota
        if nota_texto:
            hallazgos.extend(validar_nota_apa7(nota_texto))

        reporte_tablas.append({
            "indice": idx,
            "etiqueta": num_texto,
            "titulo": titulo_texto,
            "nota": nota_texto,
            "errores": hallazgos
        })

    # 2. Auditoría de Figuras
    figuras = datos_doc.get("figuras", [])
    for idx, fig in enumerate(figuras, start=1):
        hallazgos = []
        num_texto = fig.get("numero_texto", "")
        titulo_texto = fig.get("titulo_texto", "")
        nota_texto = fig.get("nota_texto", "")

        if not fig.get("numero_es_negrita", False):
            hallazgos.append({
                "tipo": "figura_numero_sin_negrita",
                "mensaje": f"La etiqueta '{num_texto}' debe estar completamente en negrita."
            })

        if not fig.get("titulo_es_cursiva", False):
            hallazgos.append({
                "tipo": "figura_titulo_sin_cursiva",
                "mensaje": f"El título de la figura ('{titulo_texto}') debe estar en cursiva."
            })

        if nota_texto:
            hallazgos.extend(validar_nota_apa7(nota_texto))

        reporte_figuras.append({
            "indice": idx,
            "etiqueta": num_texto,
            "titulo": titulo_texto,
            "nota": nota_texto,
            "errores": hallazgos
        })

    return {
        "tablas": {
            "lista": reporte_tablas,
            "total_detectadas": len(reporte_tablas)
        },
        "figuras": {
            "lista": reporte_figuras,
            "total_detectadas": len(reporte_figuras)
        }
    }