import re

import docx
from docx.oxml.ns import qn

# Patrones estrictos para etiquetas canónicas APA 7 de tablas y figuras
PATRON_ETIQUETA_TABLA  = re.compile(r'^Tabla\s+\d+', re.IGNORECASE)
PATRON_ETIQUETA_FIGURA = re.compile(r'^Figura\s+\d+', re.IGNORECASE)


def es_etiqueta_elemento_visual(texto: str) -> bool:
    """Retorna True solo si el párrafo comienza con 'Tabla N' o 'Figura N' (etiqueta canónica APA 7)."""
    t = texto.strip()
    return bool(PATRON_ETIQUETA_TABLA.match(t) or PATRON_ETIQUETA_FIGURA.match(t))


def extraer_margenes(documento):
    seccion = documento.sections[0]
    return {
        "superior": round(seccion.top_margin.cm, 2),
        "inferior": round(seccion.bottom_margin.cm, 2),
        "izquierdo": round(seccion.left_margin.cm, 2),
        "derecho": round(seccion.right_margin.cm, 2),
    }


def resolver_desde_estilo(parrafo, atributo):
    valor = getattr(parrafo.paragraph_format, atributo)
    if valor is not None:
        return valor

    estilo = parrafo.style
    while estilo is not None:
        valor = getattr(estilo.paragraph_format, atributo, None)
        if valor is not None:
            return valor
        estilo = estilo.base_style

    return None


def obtener_interlineado(parrafo):
    valor = resolver_desde_estilo(parrafo, "line_spacing")
    if valor is None:
        return None
    if hasattr(valor, "pt"):
        return f"{valor.pt}pt"
    return valor


def obtener_tamano_fuente_default(documento):
    doc_defaults = documento.styles.element.find(qn('w:docDefaults'))
    if doc_defaults is None:
        return None

    rpr_default = doc_defaults.find(qn('w:rPrDefault'))
    if rpr_default is None:
        return None

    rpr = rpr_default.find(qn('w:rPr'))
    if rpr is None:
        return None

    sz = rpr.find(qn('w:sz'))
    if sz is None:
        return None

    val = sz.get(qn('w:val'))
    if val is None:
        return None

    return int(val) / 2


def obtener_fuente(parrafo, tamano_default=None):
    nombre = None
    tamano = None

    for run in parrafo.runs:
        if run.text.strip():
            if run.font.name:
                nombre = run.font.name
            if run.font.size:
                tamano = run.font.size.pt
            break

    estilo = parrafo.style
    while estilo is not None and (nombre is None or tamano is None):
        if nombre is None and estilo.font.name:
            nombre = estilo.font.name
        if tamano is None and estilo.font.size:
            tamano = estilo.font.size.pt
        estilo = estilo.base_style

    if tamano is None:
        tamano = tamano_default

    return nombre, tamano


def _texto_completo_parrafo(parrafo) -> str:
    """
    Extrae el texto completo de un párrafo incluyendo el texto dentro de nodos
    w:sdt (Content Controls), usados por Word, Mendeley y EndNote para insertar
    citas automáticas. python-docx.paragraph.text omite estos nodos.

    Usa lxml.iter() con Clark notation para evitar conflictos con el método
    xpath() sobreescrito por python-docx que inyecta su propio nsmap.
    """
    # Clark notation: {URI}localname — compatible con iter() de lxml sin sobrescrituras
    TAG_W_T = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'
    return ''.join(node.text or '' for node in parrafo._p.iter(TAG_W_T))


def _es_parrafo_portada(parrafo, indice: int, total: int) -> bool:
    """
    Heurística para detectar párrafos de portada/carátula:
    - Están en los primeros ~30 párrafos del documento
    - El texto está en MAYÚSCULAS o es muy corto (nombre de institución, título, etc.)
    - Alineación centrada
    - No tiene sangría de primera línea de cuerpo esperada
    """
    if indice > 30:
        return False
    texto = parrafo.text.strip()
    if not texto:
        return False
    alineacion_valor = resolver_desde_estilo(parrafo, "alignment")
    alineacion = alineacion_valor.name if alineacion_valor else None
    es_mayusculas = texto.isupper() or texto.replace(' ', '').replace('\n', '').isupper()
    es_centrado = alineacion in ("CENTER", "DISTRIBUTE")
    es_corto = len(texto) < 120
    return es_centrado and (es_mayusculas or es_corto) and indice < 20


def extraer_parrafos(documento):
    tamano_default = obtener_tamano_fuente_default(documento)

    # Pre-calcular total para heurística de portada
    todos_parrafos = [p for p in documento.paragraphs if p.text.strip()]
    total = len(todos_parrafos)

    parrafos = []
    indice_real = 0  # Índice sobre párrafos no vacíos

    # 1. Párrafos del cuerpo del documento (doc.paragraphs)
    for parrafo in documento.paragraphs:
        # Usar XPath para capturar texto en w:sdt (citas Mendeley/Word/EndNote)
        texto_completo = _texto_completo_parrafo(parrafo)
        if not texto_completo.strip():
            continue

        fuente_nombre, fuente_tamano = obtener_fuente(parrafo, tamano_default)
        primera_linea = parrafo.paragraph_format.first_line_indent
        izquierda = parrafo.paragraph_format.left_indent
        alineacion_valor = resolver_desde_estilo(parrafo, "alignment")
        en_portada = _es_parrafo_portada(parrafo, indice_real, total)

        parrafos.append({
            "texto": texto_completo,
            "estilo": parrafo.style.name if parrafo.style else None,  # Nombre del estilo Word (ej. 'Heading 1')
            "alineacion": alineacion_valor.name if alineacion_valor else None,
            "interlineado": obtener_interlineado(parrafo),
            "sangria_primera_linea_cm": round(primera_linea.cm, 2) if primera_linea is not None else None,
            "sangria_izquierda_cm": round(izquierda.cm, 2) if izquierda is not None else None,
            "fuente": fuente_nombre,
            "tamano_fuente_pt": fuente_tamano,
            "en_tabla": False,
            "en_portada": en_portada,
        })
        indice_real += 1

    # 2. Párrafos contenidos dentro de las tablas (doc.tables)
    celdas_vistas = set()
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                if celda._tc in celdas_vistas:
                    continue
                celdas_vistas.add(celda._tc)
                for parrafo in celda.paragraphs:
                    texto_completo = _texto_completo_parrafo(parrafo)
                    if not texto_completo.strip():
                        continue

                    fuente_nombre, fuente_tamano = obtener_fuente(parrafo, tamano_default)
                    primera_linea = parrafo.paragraph_format.first_line_indent
                    izquierda = parrafo.paragraph_format.left_indent
                    alineacion_valor = resolver_desde_estilo(parrafo, "alignment")

                    parrafos.append({
                        "texto": texto_completo,
                        "estilo": parrafo.style.name if parrafo.style else None,
                        "alineacion": alineacion_valor.name if alineacion_valor else None,
                        "interlineado": obtener_interlineado(parrafo),
                        "sangria_primera_linea_cm": round(primera_linea.cm, 2) if primera_linea is not None else None,
                        "sangria_izquierda_cm": round(izquierda.cm, 2) if izquierda is not None else None,
                        "fuente": fuente_nombre,
                        "tamano_fuente_pt": fuente_tamano,
                        "en_tabla": True,
                        "en_portada": False,
                    })

    return parrafos


def analizar_formato_parrafo(parrafo) -> dict:
    es_negrita = False
    es_cursiva = False
    if parrafo.runs:
        es_negrita = all(run.bold for run in parrafo.runs if run.text.strip())
        es_cursiva = all(run.italic for run in parrafo.runs if run.text.strip())
    return {
        "texto": parrafo.text.strip(),
        "es_negrita": es_negrita,
        "es_cursiva": es_cursiva
    }


def tiene_bordes_verticales_xml(tabla) -> bool:
    """Inspecciona la estructura XML de la tabla en busca de bordes verticales."""
    tblPr = tabla._tbl.tblPr
    tblBorders = tblPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblBorders"
    )
    if tblBorders is not None:
        for v_border in ["insideV", "left", "right"]:
            b = tblBorders.find(
                f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{v_border}"
            )
            if b is not None and b.get(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") not in (
                    "none", "nil"):
                return True
    return False


def extraer_tablas(documento):
    tablas_extraidas = []
    elementos = list(documento.element.body)

    for i, elem in enumerate(elementos):
        if elem.tag.endswith('tbl'):
            tbl_obj = documento.tables[elementos[:i].count(elem)]

            # Buscar párrafos previos con texto
            parrafos_previos = [
                p for p in documento.paragraphs
                if p._element in elementos[:i] and p.text.strip()
            ]
            # Buscar hacia atrás la etiqueta canónica APA: 'Tabla N' o 'Figura N'
            p_numero_raw = next(
                (p for p in reversed(parrafos_previos)
                 if es_etiqueta_elemento_visual(p.text)),
                None
            )
            p_numero = analizar_formato_parrafo(p_numero_raw) if p_numero_raw else {}

            # El título es el párrafo inmediatamente posterior a la etiqueta
            if p_numero_raw and p_numero_raw in parrafos_previos:
                idx_num = parrafos_previos.index(p_numero_raw)
                p_titulo_raw = (
                    parrafos_previos[idx_num + 1]
                    if idx_num + 1 < len(parrafos_previos) else None
                )
                p_titulo = analizar_formato_parrafo(p_titulo_raw) if p_titulo_raw else {}
            else:
                p_titulo = {}

            # Buscar párrafos posteriores con texto (Nota)
            parrafos_posteriores = [
                p for p in documento.paragraphs
                if p._element in elementos[i:] and p.text.strip()
            ]
            p_nota = analizar_formato_parrafo(parrafos_posteriores[0]) if parrafos_posteriores else {}

            texto_nota = p_nota.get("texto", "")
            nota_limpia = texto_nota if texto_nota.lower().startswith("nota") else ""

            tablas_extraidas.append({
                "numero_texto": p_numero.get("texto", ""),
                "numero_es_negrita": p_numero.get("es_negrita", False),
                "titulo_texto": p_titulo.get("texto", ""),
                "titulo_es_cursiva": p_titulo.get("es_cursiva", False),
                "nota_texto": nota_limpia,
                "lineas_verticales": tiene_bordes_verticales_xml(tbl_obj)
            })

    return tablas_extraidas


def extraer_docx(ruta_archivo):
    documento = docx.Document(ruta_archivo)
    return {
        "margenes": extraer_margenes(documento),
        "parrafos": extraer_parrafos(documento),
        "tablas": extraer_tablas(documento),
    }


if __name__ == "__main__":
    import json
    import sys

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    resultado = extraer_docx(ruta)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))