"""
reporte_pdf.py — Generador de PDF de auditoría APA 7 con identidad visual RigHo.
v2.0 Refactor Master: Sanitización Unicode, CTA dinámico con nivel de riesgo,
enlace WhatsApp pre-llenado y escape robusto para ReportLab.

Características:
  - NumberedCanvas para paginación real "Página X de Y" en dos pasadas
  - Marca de agua diagonal semitransparente en todas las páginas
  - Pie de página con datos de contacto oficiales
  - Semáforo de Riesgo de Aprobación en lugar de porcentaje
  - Muestreo: 100% para cruce crítico; max 30 para formato/gramática
  - Bloque CTA dinámico con nivel de riesgo en URL WhatsApp
  - Sanitización completa de caracteres Unicode para ReportLab
"""
import gc
import html
import json
import os
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Paleta RigHo
# ---------------------------------------------------------------------------
RIGHO_NAVY     = colors.HexColor("#0F2537")
RIGHO_CYAN     = colors.HexColor("#00A8E8")
RIGHO_CYAN_LT  = colors.HexColor("#E6F7FF")
RIGHO_LIGHT    = colors.HexColor("#F0F4F8")
RIGHO_GRAY     = colors.HexColor("#4A5568")
ACCENT_RED     = colors.HexColor("#C53030")
ACCENT_GREEN   = colors.HexColor("#276749")
ACCENT_AMBER   = colors.HexColor("#B7791F")
BORDER_CYAN    = colors.HexColor("#BEE3F8")
HEADER_BG      = colors.HexColor("#D1ECF8")

# Colores semáforo
SEM_RED    = colors.HexColor("#FFF5F5")
SEM_AMBER  = colors.HexColor("#FFFBEB")
SEM_GREEN  = colors.HexColor("#F0FFF4")
SEM_RED_BRD   = colors.HexColor("#FC8181")
SEM_AMBER_BRD = colors.HexColor("#F6AD55")
SEM_GREEN_BRD = colors.HexColor("#68D391")

# Datos de contacto oficiales
BRAND = "RigHo"
WHATSAPP = "+51 917 313 145"
WHATSAPP_NUM = "51917313145"  # para URLs wa.me
INSTAGRAM = "@righo.pe"


# ---------------------------------------------------------------------------
# Sanitización de texto Unicode para ReportLab (v2.0)
# ---------------------------------------------------------------------------
# Tabla de traducción: reemplaza caracteres problemáticos por equivalentes ASCII/Latin
_UNICODE_SANITIZE_MAP = {
    # Comillas tipográficas
    '\u2018': "'",   # ' comilla simple izquierda
    '\u2019': "'",   # ' comilla simple derecha
    '\u201C': '"',   # " comilla doble izquierda
    '\u201D': '"',   # " comilla doble derecha
    '\u201E': '"',   # „ comilla doble baja
    '\u201F': '"',   # ‟ comilla doble alta invertida
    '\u2032': "'",   # ′ prima
    '\u2033': '"',   # ″ doble prima
    # Guiones tipográficos
    '\u2013': '-',   # – guión en (en dash)
    '\u2014': '--',  # — guión em (em dash)
    '\u2015': '--',  # ― guión horizontal
    '\u2012': '-',   # ‒ guión figura
    # Viñetas y símbolos problemáticos
    '\u2022': '*',   # • viñeta
    '\u2023': '>',   # ‣ viñeta triangular
    '\u25CF': '*',   # ● círculo sólido
    '\u25CB': 'o',   # ○ círculo vacío
    '\u25A0': '[x]', # ■ cuadrado sólido
    '\u25A1': '[ ]', # □ cuadrado vacío
    # Elipsis y espacios especiales
    '\u2026': '...',  # … elipsis
    '\u00A0': ' ',    # espacio no rompe
    '\u2009': ' ',    # espacio fino
    '\u200B': '',     # espacio de ancho cero
    '\u200C': '',     # no joiner
    '\u200D': '',     # joiner de ancho cero
    '\uFEFF': '',     # BOM
    # Símbolos de copyright/trademark
    '\u00AE': '(R)',  # ®
    '\u2122': '(TM)', # ™
    '\u00A9': '(c)',  # ©
    # Flechas
    '\u2192': '->',   # →
    '\u2190': '<-',   # ←
    '\u2194': '<->',  # ↔
    # Símbolos matemáticos problemáticos en PDF
    '\u00D7': 'x',    # × multiplicación
    '\u00F7': '/',    # ÷ división
    '\u2265': '>=',   # ≥
    '\u2264': '<=',   # ≤
    '\u2260': '!=',   # ≠
    '\u00B1': '+/-',  # ±
}


def sanitizar_para_pdf(texto: str) -> str:
    """
    Sanitiza texto para uso seguro en ReportLab/PDF.
    - Reemplaza caracteres Unicode problemáticos por equivalentes ASCII/Latin.
    - Elimina caracteres de control y caracteres no imprimibles.
    - Limpia dobles espacios resultantes de la sanitización.
    """
    if not texto:
        return ""

    texto_str = str(texto)

    # 1. Aplicar tabla de traducción de caracteres problemáticos
    for char, reemplazo in _UNICODE_SANITIZE_MAP.items():
        texto_str = texto_str.replace(char, reemplazo)

    # 2. Eliminar caracteres de control (excepto saltos de línea y tabulaciones)
    texto_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', texto_str)

    # 3. Filtrar cualquier carácter no-ASCII que no sea Latin-1 extendido (seguro en ReportLab Helvetica)
    # Preservar: ASCII (0-127) + Latin-1 supplement (128-255) típicos del español
    resultado = []
    for char in texto_str:
        codigo = ord(char)
        if codigo <= 255:
            resultado.append(char)
        else:
            # Intentar transliteración básica para otros caracteres
            try:
                import unicodedata
                nombre = unicodedata.name(char, '')
                if 'LATIN' in nombre:
                    # Normalizar NFD y extraer base ASCII
                    nfd = unicodedata.normalize('NFD', char)
                    base = nfd[0] if nfd and ord(nfd[0]) < 256 else '?'
                    resultado.append(base)
                else:
                    resultado.append('?')
            except Exception:
                resultado.append('?')

    texto_sanitizado = ''.join(resultado)

    # 4. Limpiar dobles espacios resultantes
    texto_sanitizado = re.sub(r'  +', ' ', texto_sanitizado).strip()

    return texto_sanitizado


def escape_txt(texto: str) -> str:
    """Escapa HTML/XML y sanitiza Unicode para uso seguro en ReportLab."""
    if not texto:
        return ""
    return html.escape(sanitizar_para_pdf(str(texto)))


# ---------------------------------------------------------------------------
# Semáforo de Riesgo
# ---------------------------------------------------------------------------
def _clasificar_riesgo(huerfanas, discrepancias, sin_usar,
                        total_formato, total_gramatica):
    """
    Clasifica el nivel de riesgo de aprobación:
      🔴 ALTO    — citas huérfanas, discrepancias de año o errores gramaticales severos
      🟡 MODERADO — referencias sin usar, observaciones de formato o gramática leve
      🟢 BAJO    — cumplimiento alto de APA 7
    """
    n_huerfanas   = len(huerfanas)
    n_discrepancias = len(discrepancias)

    if n_huerfanas > 0 or n_discrepancias > 0 or total_gramatica > 15:
        return "ALTO"
    if len(sin_usar) > 0 or total_formato > 20 or total_gramatica > 0:
        return "MODERADO"
    return "BAJO"


def _semaforo_datos(nivel: str) -> dict:
    configs = {
        "ALTO": {
            "emoji": "RIESGO ALTO",
            "label": "RIESGO ALTO",
            "sublabel": "Revision urgente recomendada",
            "detalle": (
                "Se detectaron citas huerfanas, discrepancias de anio "
                "o errores gramaticales que pueden afectar la aprobacion."
            ),
            "bg": SEM_RED,
            "brd": SEM_RED_BRD,
            "txt_color": "#C53030",
            "nivel_url": "Alto",
        },
        "MODERADO": {
            "emoji": "RIESGO MODERADO",
            "label": "RIESGO MODERADO",
            "sublabel": "Ajustes de formato necesarios",
            "detalle": (
                "Las citas y referencias estan en orden, pero existen "
                "observaciones de formato, interlineado o uso de referencias "
                "sin citar que deben corregirse."
            ),
            "bg": SEM_AMBER,
            "brd": SEM_AMBER_BRD,
            "txt_color": "#B7791F",
            "nivel_url": "Moderado",
        },
        "BAJO": {
            "emoji": "RIESGO BAJO",
            "label": "RIESGO BAJO",
            "sublabel": "Listo para revision del jurado",
            "detalle": (
                "El documento presenta un cumplimiento alto de APA 7. "
                "Solo se requieren ajustes menores antes de la sustentacion."
            ),
            "bg": SEM_GREEN,
            "brd": SEM_GREEN_BRD,
            "txt_color": "#276749",
            "nivel_url": "Bajo",
        },
    }
    return configs[nivel]


def _generar_url_whatsapp(nivel_riesgo: str, documento: str = "") -> str:
    """Genera una URL de WhatsApp con mensaje pre-llenado indicando el nivel de riesgo."""
    import urllib.parse
    nombre_doc = sanitizar_para_pdf(documento) if documento else "mi documento"
    mensaje = (
        f"Hola RigHo, acabo de auditar '{nombre_doc}' con su plataforma "
        f"y el nivel de riesgo detectado es: {nivel_riesgo}. "
        "Me gustaria recibir asesoria personalizada para levantar las observaciones."
    )
    return f"https://wa.me/{WHATSAPP_NUM}?text={urllib.parse.quote(mensaje)}"


# ---------------------------------------------------------------------------
# NumberedCanvas — paginación real "Página X de Y"
# ---------------------------------------------------------------------------
class _NumberedCanvas(rl_canvas.Canvas):
    """
    Canvas personalizado que almacena el estado de cada página durante el
    build y en save() los reproduce añadiendo watermark + footer con el
    total de páginas ya conocido.
    """

    def __init__(self, *args, **kwargs):
        rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._page_states: list[dict] = []

    def showPage(self):
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._page_states)
        for i, state in enumerate(self._page_states, start=1):
            self.__dict__.update(state)
            self._draw_watermark()
            self._draw_footer(page_num=i, total=total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_watermark(self):
        page_w, page_h = letter
        self.saveState()
        self.setFont("Helvetica-Bold", 36)
        self.setFillColor(colors.Color(0.80, 0.84, 0.88, alpha=0.15))
        self.translate(page_w / 2, page_h / 2)
        self.rotate(42)
        self.drawCentredString(0, 14, "RIGHO  AUDITORIA ACADEMICA")
        self.restoreState()

    def _draw_footer(self, page_num: int, total: int):
        page_w, _ = letter
        self.saveState()

        # Línea separadora cian
        self.setStrokeColor(RIGHO_CYAN)
        self.setLineWidth(0.8)
        self.line(28, 28, page_w - 28, 28)

        # Texto footer
        self.setFont("Helvetica", 6.5)
        self.setFillColor(RIGHO_GRAY)
        left = f"RigHo | Diagnostico automatizado | WhatsApp: {WHATSAPP} | Instagram: {INSTAGRAM}"
        right = f"Pagina {page_num} de {total}"
        self.drawString(28, 17, left)
        self.drawRightString(page_w - 28, 17, right)
        self.restoreState()


# ---------------------------------------------------------------------------
# Estilos tipográficos
# ---------------------------------------------------------------------------
def _build_styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        parent = kw.pop("parent", base["Normal"])
        return ParagraphStyle(name, parent=parent, **kw)

    return {
        "report_title": ps(
            "ReportTitle",
            fontName="Helvetica-Bold", fontSize=17, leading=21,
            textColor=RIGHO_NAVY, spaceAfter=2,
        ),
        "report_sub": ps(
            "ReportSub",
            fontName="Helvetica", fontSize=9, leading=13,
            textColor=RIGHO_CYAN, spaceAfter=10,
        ),
        "h2": ps(
            "SectionH2",
            fontName="Helvetica-Bold", fontSize=11, leading=15,
            textColor=RIGHO_NAVY, spaceBefore=14, spaceAfter=6,
        ),
        "body": ps(
            "Body",
            fontName="Helvetica", fontSize=8.5, leading=12,
            textColor=RIGHO_GRAY,
        ),
        "error": ps(
            "ErrorMsg",
            fontName="Helvetica-Bold", fontSize=8.5, leading=12,
            textColor=ACCENT_RED,
        ),
        "footnote": ps(
            "Footnote",
            fontName="Helvetica-Oblique", fontSize=7.5, leading=10,
            textColor=RIGHO_GRAY,
        ),
        "sem_title": ps(
            "SemTitle",
            fontName="Helvetica-Bold", fontSize=14, leading=18,
            textColor=RIGHO_NAVY, alignment=1,
        ),
        "sem_nivel": ps(
            "SemNivel",
            fontName="Helvetica-Bold", fontSize=12, leading=16,
            alignment=1,
        ),
        "sem_sub": ps(
            "SemSub",
            fontName="Helvetica-Oblique", fontSize=9, leading=12,
            alignment=1,
        ),
        "sem_det": ps(
            "SemDet",
            fontName="Helvetica", fontSize=8, leading=11,
            textColor=RIGHO_GRAY, alignment=1,
        ),
        "kpi": ps(
            "KPI",
            fontName="Helvetica", fontSize=8.5, leading=12,
            textColor=RIGHO_GRAY,
        ),
        "cta": ps(
            "CTA",
            fontName="Helvetica", fontSize=9.5, leading=14,
            textColor=RIGHO_NAVY,
        ),
    }


# ---------------------------------------------------------------------------
# Helpers UI
# ---------------------------------------------------------------------------
def _section_hr():
    return HRFlowable(width="100%", thickness=0.8, color=RIGHO_CYAN, spaceAfter=6)


def _table_style():
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR",     (0, 0), (-1, 0), RIGHO_NAVY),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8.5),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER_CYAN),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ])


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------
def generar_reporte_pdf(
    datos_json: dict,
    ruta_pdf_salida: str = "reporte_diagnostico_apa.pdf",
):
    """
    Genera el PDF de auditoría APA 7 con identidad visual RigHo completa.
    v2.0: Sanitización Unicode total, CTA dinámico con nivel de riesgo en WhatsApp URL.
    """
    S = _build_styles()

    # ── Extracción de datos ───────────────────────────────────────────
    citas_obj     = datos_json.get("citas", {})
    citas_list    = citas_obj.get("lista", []) if isinstance(citas_obj, dict) else []
    total_citas   = citas_obj.get("total_detectadas", len(citas_list)) if isinstance(citas_obj, dict) else 0
    citas_err     = sum(1 for c in citas_list if c.get("errores"))

    ref_obj       = datos_json.get("referencias", {})
    ref_list      = ref_obj.get("lista", []) if isinstance(ref_obj, dict) else []
    total_ref     = len(ref_list)
    ref_err       = sum(1 for r in ref_list if r.get("errores"))

    tablas_fig    = datos_json.get("tablas_y_figuras", {})
    tablas_list   = tablas_fig.get("tablas", {}).get("lista", [])
    figuras_list  = tablas_fig.get("figuras", {}).get("lista", [])
    tf_list       = tablas_list + figuras_list
    total_tf      = len(tf_list)
    tf_err        = sum(1 for t in tf_list if t.get("errores"))

    cruce         = datos_json.get("cruce_citas_referencias", {})
    huerfanas     = cruce.get("citas_huerfanas", [])
    sin_usar      = cruce.get("referencias_sin_usar", [])
    discrepancias = cruce.get("discrepancias_anio", [])
    total_cruce   = len(huerfanas) + len(sin_usar) + len(discrepancias)

    formato_list  = datos_json.get("formato", [])
    if not isinstance(formato_list, list):
        formato_list = []
    total_formato = len(formato_list)

    titulos_obj   = datos_json.get("titulos", {})
    titulos_list  = titulos_obj.get("lista", []) if isinstance(titulos_obj, dict) else []
    total_titulos = len(titulos_list)
    titulos_err   = [t for t in titulos_list if t.get("errores")]
    total_tit_err = len(titulos_err)

    gram_act      = datos_json.get("gramatica_activada", False)
    gram_obj      = datos_json.get("gramatica", {})
    gram_list     = gram_obj.get("lista", []) if isinstance(gram_obj, dict) else []
    total_gram    = len(gram_list)

    total_global  = (
        citas_err + ref_err + tf_err + total_cruce
        + total_formato + total_tit_err
        + (total_gram if gram_act else 0)
    )

    doc_nombre = sanitizar_para_pdf(datos_json.get("documento", "Documento"))

    # Semáforo
    nivel_riesgo  = _clasificar_riesgo(
        huerfanas, discrepancias, sin_usar, total_formato, total_gram
    )
    sem           = _semaforo_datos(nivel_riesgo)
    url_whatsapp  = _generar_url_whatsapp(sem["nivel_url"], doc_nombre)

    # ── Doc base ─────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        ruta_pdf_salida,
        pagesize=letter,
        rightMargin=36, leftMargin=36,
        topMargin=40, bottomMargin=48,
    )

    story = []

    # ══════════════════════════════════════════════════════════════════
    # 1. CABECERA RIGHO
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph(
        "INFORME DE DIAGNOSTICO Y AUDITORIA APA 7.",
        S["report_title"],
    ))
    story.append(Paragraph(
        f"Generado por RigHo | Consultoria en Investigacion ({INSTAGRAM}) &nbsp;·&nbsp; "
        f"<i>{escape_txt(doc_nombre)}</i>",
        S["report_sub"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=2.5, color=RIGHO_CYAN, spaceAfter=14
    ))

    # ══════════════════════════════════════════════════════════════════
    # 2. RESUMEN EJECUTIVO
    # ══════════════════════════════════════════════════════════════════
    story.append(Paragraph("Resumen Ejecutivo", S["h2"]))

    # ── 2a. Semáforo de Riesgo ────────────────────────────────────────
    sem_left = Table(
        [[Paragraph("SEMAFORO DE RIESGO DE APROBACION", S["sem_title"])]],
        colWidths=[198],
    )
    sem_left.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), sem["bg"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    nivel_style = ParagraphStyle(
        "NivelDyn",
        parent=S["sem_nivel"],
        textColor=colors.HexColor(sem["txt_color"]),
    )
    sub_style = ParagraphStyle(
        "SubDyn",
        parent=S["sem_sub"],
        textColor=colors.HexColor(sem["txt_color"]),
    )

    sem_content = [
        [Paragraph(f"{sem['label']}", nivel_style)],
        [Paragraph(sem["sublabel"], sub_style)],
        [Spacer(1, 4)],
        [Paragraph(sem["detalle"], S["sem_det"])],
    ]
    sem_inner = Table(sem_content, colWidths=[198])
    sem_inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), sem["bg"]),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    # Celda derecha: métricas directas
    def _metric(label, val, color_val=None):
        return Paragraph(
            f"<b>{label}:</b>  "
            f"<font color='{color_val or '#0F2537'}'><b>{val}</b></font>",
            S["kpi"],
        )

    col_err = "#C53030"
    col_ok  = "#276749"

    metricas_rows = [
        [_metric("Citas en texto analizadas", total_citas, "#0F2537")],
        [_metric("Referencias bibliograficas", total_ref, "#0F2537")],
        [_metric(
            "Inconsistencias de validacion cruzada",
            total_cruce,
            col_err if total_cruce else col_ok,
        )],
        [_metric(
            "Observaciones de formato general",
            total_formato,
            col_err if total_formato > 20 else col_ok,
        )],
        [_metric(
            "Hallazgos gramaticales / sintaxis",
            total_gram if gram_act else "No activado",
            col_err if total_gram > 10 else col_ok,
        )],
    ]
    sem_right = Table(metricas_rows, colWidths=[340])
    sem_right.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RIGHO_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, BORDER_CYAN),
    ]))

    brd_hex = sem["brd"].hexval() if hasattr(sem["brd"], "hexval") else "#FC8181"
    tbl_sem = Table([[sem_inner, sem_right]], colWidths=[200, 342])
    tbl_sem.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1.5, colors.HexColor(brd_hex)),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    story.append(tbl_sem)
    story.append(Spacer(1, 10))

    # ── 2b. KPI cards (2×3) ───────────────────────────────────────────
    def kpi_cell(label, total, errores, err_label="Con errores"):
        col = col_err if errores else col_ok
        return Paragraph(
            f"<b>{label}:</b> {total}<br/>"
            f"<font color='{col}'>{err_label}: {errores}</font>",
            S["kpi"],
        )

    data_kpi = [
        [
            kpi_cell("Citas en Texto", total_citas, citas_err),
            kpi_cell("Referencias", total_ref, ref_err),
            kpi_cell("Cruce Citas-Refs", "", total_cruce, "Inconsistencias"),
        ],
        [
            kpi_cell("Tablas / Figuras", total_tf, tf_err, "Con obs."),
            kpi_cell("Jerarquia Titulos", total_titulos, total_tit_err, "Con obs."),
            Paragraph(
                f"<b>Formato:</b> {total_formato} obs.<br/>"
                + (f"<font color='{col_err if total_gram > 10 else col_ok}'>"
                   f"Gramatica: {total_gram} errores</font>"
                   if gram_act else "<b>Gramatica:</b> Desactivada"),
                S["kpi"],
            ),
        ],
    ]
    tbl_kpi = Table(data_kpi, colWidths=[180, 180, 182])
    tbl_kpi.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RIGHO_LIGHT),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER_CYAN),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl_kpi)
    story.append(Spacer(1, 8))

    # Estado global
    if total_global == 0:
        estado = ("<font color='#276749'><b>Excelente! No se detectaron errores "
                  "ni descalces en la auditoria APA 7.</b></font>")
    else:
        estado = (f"<font color='#C53030'><b>Se identificaron {total_global} "
                  f"observaciones que requieren revision bajo APA 7.</b></font>")
    story.append(Paragraph(estado, S["body"]))
    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════
    # Sección helper
    # ══════════════════════════════════════════════════════════════════
    def add_section(titulo):
        story.append(Paragraph(sanitizar_para_pdf(titulo), S["h2"]))
        story.append(_section_hr())

    def add_table(rows, col_widths):
        t = Table(rows, colWidths=col_widths)
        t.setStyle(_table_style())
        story.append(t)

    def add_sampling_note(mostrados, total, tipo="observaciones de formato", genero="f"):
        if total > mostrados:
            art = "las" if genero == "f" else "los"
            adj = "representativas" if genero == "f" else "representativos"
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<i>* Se muestran {art} {mostrados} {tipo} mas {adj} "
                f"de {total} totales. Consulte el reporte detallado para la lista completa.</i>",
                S["footnote"],
            ))

    # ══════════════════════════════════════════════════════════════════
    # 3. CRUCE CITAS ↔ REFERENCIAS  (100% de errores — crítico)
    # ══════════════════════════════════════════════════════════════════
    add_section("1. Cruce entre Citas en Texto y Referencias")

    if total_cruce == 0:
        story.append(Paragraph(
            "Todas las citas en texto coinciden correctamente con la lista de referencias.",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Categoria</b>", S["body"]),
            Paragraph("<b>Detalle / Mensaje</b>", S["body"]),
        ]]
        for h in huerfanas:
            rows.append([
                Paragraph(f"Cita Huerfana: <b>{escape_txt(h.get('cita'))}</b>", S["body"]),
                Paragraph(escape_txt(h.get("mensaje")), S["error"]),
            ])
        for d in discrepancias:
            rows.append([
                Paragraph(f"Discordancia Anio: <b>{escape_txt(d.get('autor'))}</b>", S["body"]),
                Paragraph(escape_txt(d.get("mensaje")), S["error"]),
            ])
        for s in sin_usar:
            rows.append([
                Paragraph(f"Ref. No Citada: <b>{escape_txt(s.get('autor'))}</b>", S["body"]),
                Paragraph(escape_txt(s.get("mensaje")), S["error"]),
            ])
        add_table(rows, [180, 362])

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════
    # 4. FORMATO EN REFERENCIAS  (100% de errores)
    # ══════════════════════════════════════════════════════════════════
    add_section("2. Formato en Lista de Referencias")
    ref_errores = [r for r in ref_list if r.get("errores")]

    if not ref_errores:
        story.append(Paragraph(
            "No se encontraron errores formales dentro de las referencias bibliograficas.",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Referencia</b>", S["body"]),
            Paragraph("<b>Error Detectado (APA 7)</b>", S["body"]),
        ]]
        for r in ref_errores:
            ref_txt = escape_txt(r.get("texto_completo") or r.get("autores_raw", "Referencia"))
            msgs = [f"- {escape_txt(e.get('mensaje'))}" for e in r.get("errores", [])]
            rows.append([
                Paragraph(ref_txt, S["body"]),
                Paragraph("<br/>".join(msgs), S["error"]),
            ])
        add_table(rows, [280, 262])

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════
    # 5. TABLAS Y FIGURAS  (100% — usualmente pocos)
    # ══════════════════════════════════════════════════════════════════
    add_section("3. Tablas y Figuras")
    tf_errores = [tf for tf in tf_list if tf.get("errores")]

    if not tf_errores:
        story.append(Paragraph(
            "Todas las tablas y figuras cumplen con la estructura esperada.",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Elemento</b>", S["body"]),
            Paragraph("<b>Observacion</b>", S["body"]),
        ]]
        for item in tf_errores:
            nombre = escape_txt(item.get("etiqueta") or item.get("titulo") or "Elemento Visual")
            msgs   = [f"- {escape_txt(e.get('mensaje'))}" for e in item.get("errores", [])]
            rows.append([
                Paragraph(nombre, S["body"]),
                Paragraph("<br/>".join(msgs), S["error"]),
            ])
        add_table(rows, [180, 362])

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════
    # 6. FORMATO GENERAL  (max 30 — puede ser muy extenso)
    # ══════════════════════════════════════════════════════════════════
    LIMITE_FMT = 30
    add_section("4. Formato General del Documento")

    if not formato_list:
        story.append(Paragraph(
            "El documento cumple con los estandares generales de formato APA 7 "
            "(margenes, interlineado, fuente y sangria).",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Tipo de Regla</b>", S["body"]),
            Paragraph("<b>Extracto / Contexto</b>", S["body"]),
            Paragraph("<b>Observacion</b>", S["body"]),
        ]]
        for fmt in formato_list[:LIMITE_FMT]:
            rows.append([
                Paragraph(f"<b>{escape_txt(fmt.get('tipo', '').capitalize())}</b>", S["body"]),
                Paragraph(escape_txt(fmt.get("parrafo", "N/A")), S["body"]),
                Paragraph(escape_txt(fmt.get("mensaje", "")), S["error"]),
            ])
        add_table(rows, [90, 240, 212])
        add_sampling_note(LIMITE_FMT, total_formato, "observaciones de formato")

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════
    # 7. JERARQUÍA DE TÍTULOS  (100% — usualmente pocos)
    # ══════════════════════════════════════════════════════════════════
    add_section("5. Jerarquia de Titulos (Niveles APA 7)")

    if not titulos_err:
        story.append(Paragraph(
            "Todos los titulos y encabezados analizados cumplen con la jerarquia y formato de APA 7.",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Encabezado / Nivel</b>", S["body"]),
            Paragraph("<b>Observaciones (APA 7)</b>", S["body"]),
        ]]
        for item in titulos_err:
            nivel   = item.get("nivel", "?")
            txt     = escape_txt(item.get("texto", ""))
            estilo  = escape_txt(item.get("estilo_word", ""))
            msgs    = [f"- {escape_txt(e.get('mensaje'))}" for e in item.get("errores", [])]
            rows.append([
                Paragraph(f"<b>Nivel {nivel}</b> ({estilo})<br/>{txt}", S["body"]),
                Paragraph("<br/>".join(msgs), S["error"]),
            ])
        add_table(rows, [200, 342])

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════
    # 8. GRAMÁTICA  (max 30 — puede ser muy extenso)
    # ══════════════════════════════════════════════════════════════════
    LIMITE_GRAM = 30
    add_section("6. Revision Ortografica y Sintactica")

    if not gram_act:
        story.append(Paragraph(
            "<i>El analisis ortografico no fue activado en esta ejecucion. "
            "Ejecute con el parametro <b>--gramatica</b> para incluirlo.</i>",
            S["body"],
        ))
    elif total_gram == 0:
        story.append(Paragraph(
            "No se detectaron faltas ortograficas ni errores sintacticos.",
            S["body"],
        ))
    elif gram_list and "error" in gram_list[0]:
        story.append(Paragraph(
            f"<font color='#C53030'><b>Aviso:</b> "
            f"{escape_txt(gram_list[0]['error'])}</font>",
            S["body"],
        ))
    else:
        rows = [[
            Paragraph("<b>Fragmento con Error</b>", S["body"]),
            Paragraph("<b>Contexto del Parrafo</b>", S["body"]),
            Paragraph("<b>Sugerencia / Mensaje</b>", S["body"]),
        ]]
        for g in gram_list[:LIMITE_GRAM]:
            frag  = escape_txt(g.get("fragmento_error", ""))
            p_ext = escape_txt(g.get("parrafo_extracto", ""))
            msg   = escape_txt(g.get("mensaje", ""))
            sugs  = g.get("sugerencias", [])
            sug_s = (f"<br/><b>Sugerencias:</b> "
                     f"{', '.join(escape_txt(s) for s in sugs)}" if sugs else "")
            rows.append([
                Paragraph(f"<font color='#9B2C2C'><b>{frag}</b></font>", S["body"]),
                Paragraph(p_ext, S["body"]),
                Paragraph(f"{msg}{sug_s}", S["body"]),
            ])
        add_table(rows, [120, 240, 182])
        add_sampling_note(LIMITE_GRAM, total_gram, tipo="hallazgos gramaticales", genero="m")

    story.append(Spacer(1, 22))

    # ══════════════════════════════════════════════════════════════════
    # 9. BLOQUE CTA FINAL CON WHATSAPP DINÁMICO (v2.0)
    # ══════════════════════════════════════════════════════════════════
    cta_rows = [[
        Paragraph(
            f"<b>Deseas levantar estas observaciones y dejar tu tesis lista para el jurado?</b><br/><br/>"
            f"Nivel de Riesgo Detectado: <b>{sem['nivel_url']}</b><br/><br/>"
            "Escribenos directamente a nuestro WhatsApp oficial: "
            f"<b>{WHATSAPP}</b><br/>"
            f"o por Instagram: <b>{INSTAGRAM}</b><br/><br/>"
            f"<font size='8.5'><b>RigHo | Consultoria en Investigacion Academica</b></font>",
            S["cta"],
        )
    ]]
    tbl_cta = Table(cta_rows, colWidths=[542])
    tbl_cta.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RIGHO_CYAN_LT),
        ("BOX",           (0, 0), (-1, -1), 2.0, RIGHO_CYAN),
        ("LEFTPADDING",   (0, 0), (-1, -1), 18),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 18),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl_cta)

    # ══════════════════════════════════════════════════════════════════
    # BUILD con NumberedCanvas (dos pasadas internas automáticas)
    # ══════════════════════════════════════════════════════════════════
    doc.build(story, canvasmaker=_NumberedCanvas)

    # Liberación de memoria post-generación
    gc.collect()

    print(f"[OK] Reporte PDF generado exitosamente en: {ruta_pdf_salida}")


# ---------------------------------------------------------------------------
# Entrypoint directo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if os.path.exists("reporte.json"):
        with open("reporte.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
        generar_reporte_pdf(datos, "reporte_diagnostico_apa.pdf")
    else:
        print(
            "Coloca un archivo 'reporte.json' en este directorio para probar el script."
        )