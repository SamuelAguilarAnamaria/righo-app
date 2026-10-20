import json
import os
import re
import sys

PALABRAS_NO_AUTOR = {
    "según", "de acuerdo con", "conforme a", "afirma", "expresa", "menciona", "para", "con", "en", "por",
    "asimismo", "además", "finalmente", "como", "revelan", "señala", "señalan", "propone",
    "hallaron", "encontró", "encontraron", "estudio", "investigación", "trabajo", "teoría", "teorías",
    "aportes", "escala", "adaptación", "modelo", "resultados", "se", "este", "esta", "estos", "estas",
    "otro", "otra", "otros", "otras", "sobre", "acerca", "donde", "cuando", "cada", "todo", "todos",
    "todas", "respecto", "también", "posteriormente", "anteriormente", "así", "mismo", "por tanto",
    "desarrollo", "funcionalidad", "procrastinación", "académica", "familiar", "poblacional",
    "constructiva", "decisiones", "procrastinadores", "español", "familia", "inesperados", "tarea",
    "proceso", "aprendizaje", "conducta", "actividades", "autorregulación", "concepto", "definición",
    "dimensiones", "niveles", "relación", "postergación", "tendencia", "evaluar", "medir", "analizar",
    "objetivo", "propósito", "método", "metodología", "diseño", "muestra", "población", "instrumento",
    "perú", "turquía", "méxico", "guatemala", "colombia", "ecuador", "chile", "argentina", "españa",
    "bogotá", "cusco", "lima", "huancayo", "junín", "latinoamérica", "arequipa",
    "adaptado", "tomado", "fuente", "modificado", "elaborado", "elaboración", "nota"
}

PARTICULAS_Y_CONECTORES = {
    "de", "del", "la", "las", "los", "van", "von", "der", "di", "da", "dos", "y", "e", "&"
}


def detectar_errores_comunes(autores_str, tipo_cita, texto_completo=""):
    hallazgos = []

    # Error: usar "y col." o "y cols." en lugar de "et al."
    match_y_col = re.search(r'\b(y\s+col[s]?\.)', autores_str, re.IGNORECASE)
    if match_y_col:
        hallazgos.append({
            "tipo": "cita_et_al",
            "mensaje": f"Se encontró '{match_y_col.group()}', en APA 7 se debe usar 'et al.'",
            "valor_encontrado": autores_str,
        })

    # Error: usar "&" en cita narrativa fuera de paréntesis
    if tipo_cita == "narrativa" and "&" in autores_str:
        hallazgos.append({
            "tipo": "cita_ampersand",
            "mensaje": "En citas narrativas (fuera de paréntesis) se debe usar 'y' en lugar de '&'",
            "valor_encontrado": autores_str,
        })

    # Error: "et al" sin punto final
    if re.search(r'\bet\s+al\b(?!\.)', autores_str, re.IGNORECASE):
        hallazgos.append({
            "tipo": "cita_falta_punto_et_al",
            "mensaje": "En la abreviatura 'et al.' debe incluirse el punto después de 'al'",
            "valor_encontrado": autores_str,
        })

    return hallazgos


def extraer_autor_narrativo_desde_texto(texto_previo):
    if not texto_previo:
        return ""

    # 1. Quitar muletillas finales justo antes del paréntesis
    texto_previo = re.sub(
        r'\s+(en\s+el\s+año|en\s+el|en\s+año|en|del|de|el|la|los|las)\s*$',
        '',
        texto_previo,
        flags=re.IGNORECASE
    )

    # 2. Cortar en el límite de la oración más cercano
    partes = re.split(r'(?<!\bet al)(?<!\bcol)(?<!\bcols)(?<!\bp)(?<!\bpp)[.;:]\s*', texto_previo)
    texto_oracion = partes[-1].strip() if partes else texto_previo.strip()

    # 3. Tokenizar respetando variantes de "et al." / "et al" / "y col." y ampersand (&)
    texto_mod = re.sub(r'\bet\s+al\.', '___ET_AL_DOT___', texto_oracion, flags=re.IGNORECASE)
    texto_mod = re.sub(r'\bet\s+al\b', '___ET_AL_NODOT___', texto_mod, flags=re.IGNORECASE)
    texto_mod = re.sub(r'\by\s+col[s]?\.', '___Y_COL_DOT___', texto_mod, flags=re.IGNORECASE)
    texto_mod = re.sub(r'\by\s+col[s]?\b', '___Y_COL_NODOT___', texto_mod, flags=re.IGNORECASE)

    tokens = re.findall(
        r'___ET_AL_DOT___|___ET_AL_NODOT___|___Y_COL_DOT___|___Y_COL_NODOT___|[A-Za-zÁÉÍÓÚÑñáéíóúüÜ\-]+|&',
        texto_mod
    )

    if not tokens:
        return ""

    tokens_autor = []
    tiene_autor_capitalizado = False

    for token in reversed(tokens):
        token_lower = token.lower()

        if token in ("___ET_AL_DOT___", "___ET_AL_NODOT___", "___Y_COL_DOT___", "___Y_COL_NODOT___"):
            if "ET_AL_DOT" in token:
                val = "et al."
            elif "ET_AL_NODOT" in token:
                val = "et al"
            elif "Y_COL_DOT" in token:
                val = "y col."
            else:
                val = "y col"
            tokens_autor.append(val)
            continue

        if token_lower in PARTICULAS_Y_CONECTORES:
            if tiene_autor_capitalizado or any(t in ("et al.", "et al", "y col.", "y col") for t in tokens_autor):
                tokens_autor.append(token)
                continue
            else:
                break

        if token_lower in PALABRAS_NO_AUTOR:
            if tokens_autor:
                break
            else:
                continue

        es_mayuscula = token[0].isupper() or (len(token) > 1 and token[1:].isupper())
        if es_mayuscula:
            tokens_autor.append(token)
            tiene_autor_capitalizado = True
        else:
            if tokens_autor:
                break

    if not tokens_autor:
        return ""

    tokens_autor.reverse()

    while tokens_autor:
        primer_token = tokens_autor[0]
        primer_token_lower = primer_token.lower()

        if primer_token_lower in ("y", "e", "&", "en", "por", "con", "de", "del", "la", "las", "los") and not primer_token[0].isupper():
            tokens_autor.pop(0)
        else:
            break

    if not tokens_autor:
        return ""

    return " ".join(tokens_autor).strip()


# Patrón para buscar citas en el texto contemplando caracteres acentuados (ÁÉÍÓÚÑáéíóúñ)
# y formatos (Autor, Año), (Autor et al., Año), con páginas o sin fecha
REGEX_CITAS_TEXTO = re.compile(
    r'\(\s*([A-ZÁÉÍÓÚÑÜa-záéíóúñü\s,\.&-]+?)\s*,\s*(\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)(?:\s*[,:]\s*(?:p|pp)\.?\s*\d+(?:-\d+)?)?\s*\)'
)

REGEX_PARENTESIS = re.compile(
    r'\((?P<contenido>[^()]*?\b(?:\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)[^()]*?)\)'
)

REGEX_SUB_CITA = re.compile(
    r'^\s*(?P<autores>[A-ZÁÉÍÓÚÑÜa-záéíóúñü\s,\.&-]+?)\s*,\s*(?P<anio>\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)(?:\s*[,:]\s*(?:p|pp)\.?\s*\d+(?:-\d+)?)?\s*$'
)


def extraer_citas_parrafo(parrafo_obj):
    if isinstance(parrafo_obj, dict):
        texto = parrafo_obj.get("texto", "").strip()
    else:
        texto = str(parrafo_obj).strip()

    if not texto:
        return []

    citas_encontradas = []

    # 1. Citas parentéticas (soporta caracteres con tildes, sub-año, s.f. y rangos de página)
    for match_p in REGEX_PARENTESIS.finditer(texto):
        contenido = match_p.group("contenido").strip()

        # Omitir si es solamente año y página sin autor (ej: '(2019, p. 12)' o '(2020)')
        if re.match(r'^(?:\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)(?:\s*[,:]\s*(?:p|pp)\.?\s*\d+(?:-\d+)?)*$', contenido):
            continue

        sub_citas = contenido.split(';')

        for sub in sub_citas:
            sub = sub.strip()
            match_sub = REGEX_SUB_CITA.search(sub)
            if match_sub:
                autores = match_sub.group("autores").strip()
                anio = match_sub.group("anio").strip()

                autores = re.sub(
                    r'^(en|ver|véase|ej\.|citado en|cf\.|según|see|e\.g\.)\s+',
                    '', autores, flags=re.IGNORECASE
                ).strip()

                if len(autores) > 100 or autores.startswith("Tabla") or autores.startswith("Figura"):
                    continue

                errores = detectar_errores_comunes(autores, "parentetica", sub)

                citas_encontradas.append({
                    "tipo_cita": "parentetica",
                    "autores_raw": autores,
                    "anio": anio,
                    "texto_completo": f"({sub})",
                    "parrafo": texto,  # Se asigna el texto completo del párrafo
                    "errores": errores,
                })

    # 2. Citas narrativas (ej. "Alcóser (2019)")
    regex_narrativa = r'\(\s*(?P<anio>\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)(?:\s*[,:]\s*(?:p|pp)\.?\s*\d+(?:-\d+)?)?\s*\)'

    for match_n in re.finditer(regex_narrativa, texto):
        start_idx = match_n.start()
        anio = match_n.group("anio").strip()
        texto_previo = texto[:start_idx]

        autor_extraido = extraer_autor_narrativo_desde_texto(texto_previo)

        if autor_extraido and autor_extraido.lower() not in PALABRAS_NO_AUTOR and len(autor_extraido) > 1:
            texto_completo = f"{autor_extraido} ({anio})"
            errores = detectar_errores_comunes(autor_extraido, "narrativa", texto_completo)

            citas_encontradas.append({
                "tipo_cita": "narrativa",
                "autores_raw": autor_extraido,
                "anio": anio,
                "texto_completo": texto_completo,
                "parrafo": texto,  # Se asigna el texto completo del párrafo
                "errores": errores,
            })

    return citas_encontradas


def procesar_citas(datos_extraidos):
    todas_citas = []

    # 1. Párrafos normales del documento (hasta llegar a la sección formal de referencias)
    for parrafo in datos_extraidos.get("parrafos", []):
        if isinstance(parrafo, dict) and parrafo.get("en_tabla"):
            continue

        texto = parrafo.get("texto", "").strip() if isinstance(parrafo, dict) else str(parrafo).strip()

        # Detener la búsqueda sólo en el encabezado exacto de referencias (no en oraciones ni en el índice)
        if re.match(
            r'^(VI\.|6\.|V\.|VII\.|VIII\.)?\s*(REFERENCIAS|REFERENCIAS BIBLIOGRÁFICAS|BIBLIOGRAFÍA|REFERENCES)\s*$',
            texto, re.IGNORECASE
        ):
            break

        citas = extraer_citas_parrafo(parrafo)
        todas_citas.extend(citas)

    # 2. Párrafos contenidos en tablas (doc.tables)
    for parrafo in datos_extraidos.get("parrafos", []):
        if isinstance(parrafo, dict) and parrafo.get("en_tabla"):
            citas = extraer_citas_parrafo(parrafo)
            todas_citas.extend(citas)

    # 3. Textos auxiliares de tablas (notas y títulos de tablas y figuras)
    for tbl in datos_extraidos.get("tablas", []):
        for campo in ["nota_texto", "titulo_texto"]:
            txt = tbl.get(campo, "").strip()
            if txt:
                citas = extraer_citas_parrafo(txt)
                todas_citas.extend(citas)

    return todas_citas


if __name__ == "__main__":
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(directorio_actual, "..", "extraction"))
    from docx_parser import extraer_docx

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    datos = extraer_docx(ruta)
    resultado = procesar_citas(datos)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))