import json
import os
import re
import sys

# Patron de corte para detener la lectura si inician los Anexos o Apéndices
PATRON_CORTE_ANEXOS = re.compile(r'^\s*(ANEXO|ANEXOS|APÉNDICE|APENDICE)\b', re.IGNORECASE)

# Abreviaturas y ordinales comunes para evitar divisiones incorrectas del título
ABREVIATURAS = [
    (r'\bI\.\s*E\.', '__ABBR_IE__'),
    (r'\bJ\.\s*E\.\s*C\.', '__ABBR_JEC__'),
    (r'\bed\.', '__ABBR_ED__'),
    (r'\bs\.f\.', '__ABBR_SF__'),
    (r'\bn\.d\.', '__ABBR_ND__'),
    (r'\bVol\.', '__ABBR_VOL__'),
    (r'\bvol\.', '__ABBR_VOL_LOWER__'),
    (r'\bNo\.', '__ABBR_NO__'),
    (r'\bno\.', '__ABBR_NO_LOWER__'),
    (r'\bp\.', '__ABBR_P__'),
    (r'\bpp\.', '__ABBR_PP__'),
]

def proteger_texto(texto: str) -> str:
    texto_p = texto
    # Proteger ordinales (ej. 4to., 5to., 3ro., 1er., 2da., etc.)
    texto_p = re.sub(r'\b(\d+)(er|do|ro|to|vo|no|da|ra|ta|ª|º)\.', r'\1\2__DOT__', texto_p, flags=re.IGNORECASE)
    
    # Proteger letras mayúsculas aisladas con punto (ej. I. E. G. P., J. E. C., U. N. M. S. M.)
    texto_p = re.sub(r'\b([A-Z\u00C0-\u00DC])\.', r'\1__DOT__', texto_p)

    for patron, reemplazo in ABREVIATURAS:
        texto_p = re.sub(patron, reemplazo, texto_p, flags=re.IGNORECASE)
    return texto_p

def desproteger_texto(texto: str) -> str:
    texto = texto.replace('__DOT__', '.')
    remplazos = [
        ('__ABBR_IE__', 'I. E.'),
        ('__ABBR_JEC__', 'J. E. C.'),
        ('__ABBR_ED__', 'ed.'),
        ('__ABBR_SF__', 's.f.'),
        ('__ABBR_ND__', 'n.d.'),
        ('__ABBR_VOL__', 'Vol.'),
        ('__ABBR_VOL_LOWER__', 'vol.'),
        ('__ABBR_NO__', 'No.'),
        ('__ABBR_NO_LOWER__', 'no.'),
        ('__ABBR_P__', 'p.'),
        ('__ABBR_PP__', 'pp.'),
    ]
    for token, orig in remplazos:
        texto = texto.replace(token, orig)
    return texto

def es_enlace_final(texto: str) -> bool:
    """Verifica si el texto termina en un enlace o DOI (los cuales no deben llevar punto según APA 7)."""
    texto_limpio = texto.strip()
    patron = r'(https?://[^\s]+|doi\.org/[^\s]+|handle\.net/[^\s]+)$'
    return bool(re.search(patron, texto_limpio, re.IGNORECASE))

def extraer_bloque_referencias(datos_extraidos):
    """Localiza la sección final del documento a partir del encabezado de referencias."""
    parrafos = datos_extraidos.get("parrafos", [])
    inicio_idx = -1

    regex_titulo_ref = r'^(VI\.|6\.|V\.|VII\.|VIII\.)?\s*(REFERENCIAS|REFERENCIAS BIBLIOGRÁFICAS|BIBLIOGRAFÍA)\s*$'

    for i, p in enumerate(parrafos):
        texto = p["texto"].strip()
        if re.match(regex_titulo_ref, texto, re.IGNORECASE):
            inicio_idx = i + 1
            break

    if inicio_idx == -1:
        for i, p in enumerate(parrafos):
            texto = p["texto"].strip()
            if ("REFERENCIAS" in texto.upper() or "BIBLIOGRAFÍA" in texto.upper()) and len(texto) < 40:
                inicio_idx = i + 1
                break

    if inicio_idx == -1 or inicio_idx >= len(parrafos):
        return []

    return parrafos[inicio_idx:]

# Palabras clave que identifican entidades corporativas/institucionales
PALABRAS_CORPORATIVAS = {
    'ministerio', 'gobierno', 'instituto', 'institución', 'organización',
    'organismo', 'dirección', 'secretaría', 'comisión', 'departamento',
    'municipalidad', 'municipio', 'congreso', 'senado', 'parlamento',
    'universidad', 'facultad', 'escuela', 'oms', 'ops', 'onu', 'unesco',
    'unicef', 'who', 'paho', 'banco', 'fondo', 'programa', 'agencia',
    'oficina', 'centro', 'consejo', 'asociación', 'sociedad', 'federación',
}


def es_autor_corporativo(autores_raw: str) -> bool:
    """
    Determina si el autor es una entidad corporativa/institucional.
    Criterio primario: sin coma (los autores personales siempre tienen 'Apellido, Inicial.').
    Criterio secundario: contiene palabras clave de entidades conocidas.
    """
    if not autores_raw:
        return False
    # Criterio 1: sin coma separadora → corporativo
    if ',' not in autores_raw:
        return True
    # Criterio 2: contiene palabras clave corporativas (para casos como "Ministerio, X")
    texto_lower = autores_raw.lower()
    return any(palabra in texto_lower for palabra in PALABRAS_CORPORATIVAS)


def detectar_errores_referencia(texto_ref, autores, anio, doi_url):
    hallazgos = []
    texto_limpio = texto_ref.strip()

    # APA 7: Si termina en enlace web o DOI, NO lleva punto final
    if not es_enlace_final(texto_limpio):
        if not texto_limpio.endswith('.'):
            hallazgos.append({
                "tipo": "ref_falta_punto_final",
                "mensaje": "La referencia bibliográfica debe finalizar con un punto.",
                "valor_encontrado": texto_limpio[-15:] if len(texto_limpio) > 15 else texto_limpio
            })

    # Error: Ausencia de año o mal formato
    if not anio:
        hallazgos.append({
            "tipo": "ref_sin_anio",
            "mensaje": "No se detectó un año válido entre paréntesis, como (2020) o (s.f.).",
            "valor_encontrado": texto_limpio[:50]
        })

    # Error: Enlace web sin el protocolo https://
    if re.search(r'\bwww\.', texto_limpio, re.IGNORECASE) and not re.search(r'https?://www\.', texto_limpio, re.IGNORECASE):
        hallazgos.append({
            "tipo": "ref_url_sin_http",
            "mensaje": "Las URLs en APA 7 deben incluir el protocolo completo 'https://'.",
            "valor_encontrado": texto_limpio
        })

    # Las reglas de formato de autor personal NO aplican a autores corporativos
    _es_corporativo = es_autor_corporativo(autores)

    # Error: Uso indebido de "et al." en la lista de referencias
    if not _es_corporativo and "et al" in autores.lower():
        hallazgos.append({
            "tipo": "ref_et_al_no_permitido",
            "mensaje": "En la lista de referencias APA 7 no debe usarse 'et al.'; se deben listar los autores explícitamente.",
            "valor_encontrado": autores
        })

    # Error: Iniciales pegadas sin punto (ej. "Murga Bedoya, LT") — solo autores personales
    tiene_iniciales_sin_punto = (
        not _es_corporativo
        and bool(re.search(r',\s*[A-Z\u00C0-\u00DC]{2,3}(?!\.)', autores))
    )
    if tiene_iniciales_sin_punto:
        hallazgos.append({
            "tipo": "ref_iniciales_sin_punto",
            "mensaje": "Las iniciales de los nombres deben llevar punto y espacio (ej. 'L. T.' en lugar de 'LT').",
            "valor_encontrado": autores
        })

    # Error: Autor sin iniciales (ej. "Ñaupas.", "Pizarro.", "Rengifo.") — solo autores personales
    if not _es_corporativo and not tiene_iniciales_sin_punto and autores:
        tiene_inicial_valida = bool(re.search(r',\s*([A-Z\u00C0-\u00DC]\.\s*)+', autores))
        if not tiene_inicial_valida:
            hallazgos.append({
                "tipo": "ref_autor_sin_iniciales",
                "mensaje": "Falta la inicial del nombre del autor (ej. 'Ñaupas, H.').",
                "valor_encontrado": autores
            })

    return hallazgos

# Expresión regular flexible para capturar el año en referencias bibliográficas
# Permite fechas extendidas como (24 de Noviembre de 2020), (julio de 2008), o s.f.
REGEX_ANIO_REFERENCIA = re.compile(
    r'\(\s*(?:(?:\d{1,2}\s+de\s+)?[A-Za-zÁÉÍÓÚña-záéíóúñ]+\s+(?:de\s+)?)*(?P<anio>\d{4}[a-z]?|s\.?\s*f\.|n\.?\s*d\.)(?:\s*,\s*[\w\s\d-]+)?\s*\)',
    re.IGNORECASE
)


def parsear_referencia(texto_ref):
    texto_ref = texto_ref.strip()
    if not texto_ref:
        return None

    # Extracción flexible del año o fecha completa
    match_anio = REGEX_ANIO_REFERENCIA.search(texto_ref)

    if match_anio:
        anio = match_anio.group("anio")
        pos_start = match_anio.start()
        pos_end = match_anio.end()

        autores_raw = texto_ref[:pos_start].strip().rstrip(',')
        resto = texto_ref[pos_end:].strip().lstrip('.').strip()
    else:
        anio = ""
        autores_raw = ""
        resto = texto_ref

    # Identificar enlace URL o DOI
    match_link = re.search(r'(https?://\S+|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+|handle\.net/\S+)', texto_ref)
    doi_url = match_link.group(0).rstrip('.') if match_link else ""

    # Desglosar título y fuente aplicando la máscara de protección
    titulo = resto
    fuente = ""
    if resto:
        resto_protegido = proteger_texto(resto)
        partes_resto = resto_protegido.split('. ')
        if len(partes_resto) > 1:
            titulo = desproteger_texto(partes_resto[0].strip())
            fuente = desproteger_texto('. '.join(partes_resto[1:]).strip())
        else:
            titulo = desproteger_texto(resto)
            fuente = ""

    errores = detectar_errores_referencia(texto_ref, autores_raw, anio, doi_url)

    return {
        "autores_raw": autores_raw,
        "anio": anio,
        "titulo": titulo,
        "fuente": fuente,
        "doi_url": doi_url,
        "texto_completo": texto_ref,
        "errores": errores
    }

def procesar_referencias(datos_extraidos):
    parrafos_ref = extraer_bloque_referencias(datos_extraidos)
    referencias_procesadas = []

    for p in parrafos_ref:
        texto = p["texto"].strip()

        # Detener la extracción si se encuentra el inicio de la sección de Anexos/Apéndices
        if PATRON_CORTE_ANEXOS.search(texto):
            break

        if not texto or len(texto) < 15:
            continue

        ref_obj = parsear_referencia(texto)
        if ref_obj:
            referencias_procesadas.append(ref_obj)

    return referencias_procesadas

if __name__ == "__main__":
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(directorio_actual, "..", "extraction"))
    from docx_parser import extraer_docx

    ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
    datos = extraer_docx(ruta)
    resultado = procesar_referencias(datos)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))