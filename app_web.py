"""
app_web.py — Interfaz Web Local (MVP - Nivel 1) para RigHo
Auditoría y Diagnóstico Académico APA 7.ª Edición con Streamlit.
"""

import os
import sys
import tempfile
import streamlit as st

# Asegurar ruta raíz en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.extraction.docx_parser import extraer_docx
from app.engines.formato import revisar_formato
from app.engines.citas import procesar_citas
from app.engines.referencias import procesar_referencias
from app.engines.tablas_figuras import revisar_tablas_y_figuras
from app.engines.titulos import revisar_titulos
from cli import realizar_validacion_cruzada
from reporte_pdf import generar_reporte_pdf, _clasificar_riesgo, _semaforo_datos


# -----------------------------------------------------------------------------
# 1. Configuración de Página y Estilo Visual (RigHo Branding)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="RigHo — Auditoría Académica APA 7",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS Corporativo RigHo
st.markdown("""
<style>
    /* Tipografía y variables base */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3, h4, .righo-font {
        font-family: 'Outfit', sans-serif;
    }

    /* Fondo principal limpio */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Header Principal Ejecutivo */
    .righo-header {
        background: linear-gradient(135deg, #0F2537 0%, #1A3A54 100%);
        border-radius: 14px;
        padding: 30px 36px;
        color: #FFFFFF;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(15, 37, 55, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .righo-header-badge {
        display: inline-block;
        background: rgba(0, 168, 232, 0.18);
        border: 1px solid #00A8E8;
        color: #64D2FF;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        padding: 4px 12px;
        border-radius: 20px;
        margin-bottom: 12px;
    }

    .righo-header-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        color: #FFFFFF;
        line-height: 1.25;
    }

    .righo-header-title span.cyan {
        color: #00A8E8;
    }

    .righo-header-subtitle {
        color: #CBD5E1;
        font-size: 1.05rem;
        margin-top: 10px;
        margin-bottom: 0;
        font-weight: 400;
        max-width: 860px;
        line-height: 1.5;
    }

    /* Estilo Barra Lateral (Sidebar) */
    [data-testid="stSidebar"] {
        background-color: #0F2537;
        border-right: 1px solid rgba(0, 168, 232, 0.15);
    }

    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stCheckbox label,
    [data-testid="stSidebar"] span {
        color: #E2E8F0 !important;
        font-size: 0.94rem;
    }

    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
        font-weight: 700;
    }

    .sidebar-brand-box {
        padding: 10px 0 20px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }

    .sidebar-logo-text {
        font-size: 2.3rem;
        font-weight: 900;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .sidebar-logo-dot {
        color: #00A8E8;
    }

    .sidebar-logo-tagline {
        color: #94A3B8;
        font-size: 0.72rem;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        font-weight: 600;
        margin-top: -2px;
    }

    .sidebar-section-title {
        color: #64D2FF !important;
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        letter-spacing: 1.1px;
        text-transform: uppercase;
        margin: 18px 0 10px 0;
    }

    .sidebar-contact-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(0, 168, 232, 0.25);
        border-radius: 10px;
        padding: 14px 16px;
        margin-top: 24px;
    }

    .sidebar-contact-title {
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .sidebar-contact-item {
        margin: 6px 0;
        font-size: 0.88rem;
    }

    .sidebar-contact-item a {
        color: #38BDF8 !important;
        text-decoration: none;
        font-weight: 600;
        transition: color 0.2s;
    }

    .sidebar-contact-item a:hover {
        color: #7DD3FC !important;
        text-decoration: underline;
    }

    /* Botón Primario y Botón de Descarga */
    div.stButton > button:first-child,
    div.stDownloadButton > button:first-child {
        background: linear-gradient(135deg, #00A8E8 0%, #0084B6 100%) !important;
        color: #FFFFFF !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 1.6rem !important;
        box-shadow: 0 4px 14px rgba(0, 168, 232, 0.35) !important;
        transition: all 0.25s ease-in-out !important;
        width: 100%;
    }

    div.stButton > button:first-child:hover,
    div.stDownloadButton > button:first-child:hover {
        background: linear-gradient(135deg, #028fc7 0%, #006f9a 100%) !important;
        box-shadow: 0 6px 20px rgba(0, 168, 232, 0.45) !important;
        transform: translateY(-2px);
        color: #FFFFFF !important;
    }

    /* Tarjetas de Métricas */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(15, 37, 55, 0.04);
        border-top: 3.5px solid #00A8E8;
    }

    [data-testid="stMetricLabel"] {
        color: #64748B !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }

    [data-testid="stMetricValue"] {
        color: #0F2537 !important;
        font-size: 1.9rem !important;
        font-weight: 800 !important;
        font-family: 'Outfit', sans-serif !important;
    }

    /* Uploader Container */
    [data-testid="stFileUploader"] {
        background: #FFFFFF;
        border: 2px dashed #CBD5E1;
        border-radius: 12px;
        padding: 20px;
        transition: border-color 0.2s;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: #00A8E8;
    }

    /* Pestañas de detalle */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #FFFFFF;
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
        font-weight: 600;
        color: #475569;
        border: 1px solid #E2E8F0;
        border-bottom: none;
    }

    .stTabs [aria-selected="true"] {
        background-color: #0F2537 !important;
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. Barra Lateral (Sidebar)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand-box">
        <div class="sidebar-logo-text">RigHo<span class="sidebar-logo-dot">.</span></div>
        <div class="sidebar-logo-tagline">Auditoría & Consultoría Académica</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-title">⚙️ Módulos de Análisis</div>', unsafe_allow_html=True)

    # Checkboxes activos por defecto
    chk_citas = st.checkbox("Citas en Texto y Referencias (APA 7)", value=True)
    chk_tablas = st.checkbox("Tablas y Figuras", value=True)
    chk_formato = st.checkbox("Formato e Interlineado", value=True)
    chk_gramatica = st.checkbox("Gramática y Sintaxis (LanguageTool)", value=True)

    st.markdown("---")

    # Sección de Contacto Oficial
    st.markdown("""
    <div class="sidebar-contact-card">
        <div class="sidebar-contact-title">
            <span>🛡️</span> Contacto Oficial RigHo
        </div>
        <div class="sidebar-contact-item">
            <span>💬 <b>WhatsApp:</b></span><br/>
            <a href="https://wa.me/51917313145" target="_blank">+51 917 313 145</a>
        </div>
        <div class="sidebar-contact-item" style="margin-top: 10px;">
            <span>📸 <b>Instagram:</b></span><br/>
            <a href="https://instagram.com/righo.pe" target="_blank">@righo.pe</a>
        </div>
        <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 12px; line-height: 1.35;">
            Asesoría personalizada para levantamiento de observaciones de tesis y estilo editorial.
        </div>
    </div>
    """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 3. Lógica de Análisis Modular
# -----------------------------------------------------------------------------
def ejecutar_pipeline_auditoria(
    ruta_docx: str,
    analizar_citas: bool,
    analizar_tablas: bool,
    analizar_formato: bool,
    analizar_gramatica: bool
) -> dict:
    """
    Ejecuta los motores de auditoría de forma modular según las selecciones del usuario.
    """
    datos_doc = extraer_docx(ruta_docx)

    # 1. Formato y Títulos
    if analizar_formato:
        reporte_formato = revisar_formato(datos_doc)
        reporte_titulos = revisar_titulos(datos_doc)
    else:
        reporte_formato = []
        reporte_titulos = []

    # 2. Citas en texto y referencias bibliográficas
    if analizar_citas:
        reporte_citas = procesar_citas(datos_doc)
        reporte_referencias = procesar_referencias(datos_doc)
        reporte_cruce = realizar_validacion_cruzada(reporte_citas, reporte_referencias)
    else:
        reporte_citas = []
        reporte_referencias = []
        reporte_cruce = {
            "citas_huerfanas": [],
            "referencias_sin_usar": [],
            "discrepancias_anio": [],
            "resumen_cruce": {
                "total_citas": 0,
                "total_referencias": 0,
                "total_citas_huerfanas": 0,
                "total_referencias_sin_usar": 0,
                "total_discrepancias_anio": 0
            }
        }

    # 3. Tablas y Figuras
    if analizar_tablas:
        reporte_tablas_figuras = revisar_tablas_y_figuras(datos_doc)
    else:
        reporte_tablas_figuras = {
            "tablas": {"lista": [], "total_detectadas": 0},
            "figuras": {"lista": [], "total_detectadas": 0}
        }

    # 4. Gramática y Sintaxis
    if analizar_gramatica:
        try:
            from app.engines.gramatica import revisar_gramatica, cerrar_tool
            reporte_gramatica = revisar_gramatica(datos_doc)
            cerrar_tool()
        except (ImportError, RuntimeError, Exception) as exc:
            reporte_gramatica = [{"error": f"LanguageTool no disponible: {str(exc)}"}]
    else:
        reporte_gramatica = []

    # Construcción del dict compatible con reporte_pdf.py
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
            "total_errores": len(reporte_gramatica) if not (reporte_gramatica and "error" in reporte_gramatica[0]) else 0
        },
    }


def calcular_estadisticas_dashboard(reporte: dict):
    """
    Calcula las 4 métricas del dashboard y los datos del semáforo.
    """
    citas_obj = reporte.get("citas", {})
    citas_list = citas_obj.get("lista", [])
    total_citas = citas_obj.get("total_detectadas", len(citas_list))
    citas_err = sum(1 for c in citas_list if c.get("errores"))

    ref_obj = reporte.get("referencias", {})
    ref_list = ref_obj.get("lista", [])
    ref_err = sum(1 for r in ref_list if r.get("errores"))

    tf_obj = reporte.get("tablas_y_figuras", {})
    tablas_list = tf_obj.get("tablas", {}).get("lista", [])
    figuras_list = tf_obj.get("figuras", {}).get("lista", [])
    tf_err = sum(1 for item in (tablas_list + figuras_list) if item.get("errores"))

    cruce = reporte.get("cruce_citas_referencias", {})
    huerfanas = cruce.get("citas_huerfanas", [])
    discrepancias = cruce.get("discrepancias_anio", [])
    sin_usar = cruce.get("referencias_sin_usar", [])
    total_inconsistencias = len(huerfanas) + len(discrepancias) + len(sin_usar)

    formato_list = reporte.get("formato", [])
    total_formato = len(formato_list)

    titulos_obj = reporte.get("titulos", {})
    titulos_list = titulos_obj.get("lista", [])
    tit_err = sum(1 for t in titulos_list if t.get("errores"))

    gram_act = reporte.get("gramatica_activada", False)
    gram_obj = reporte.get("gramatica", {})
    gram_list = gram_obj.get("lista", [])
    tiene_error_gram = (len(gram_list) > 0 and "error" in gram_list[0])
    total_gram = len(gram_list) if (gram_act and not tiene_error_gram) else 0

    total_observaciones = (
        citas_err + ref_err + tf_err + total_inconsistencias
        + total_formato + tit_err + total_gram
    )

    nivel_riesgo = _clasificar_riesgo(
        huerfanas, discrepancias, sin_usar, total_formato, total_gram
    )
    sem_info = _semaforo_datos(nivel_riesgo)

    return {
        "total_observaciones": total_observaciones,
        "total_citas": total_citas,
        "total_inconsistencias": total_inconsistencias,
        "total_gram": total_gram if gram_act else "Desactivado",
        "nivel_riesgo": nivel_riesgo,
        "sem_info": sem_info,
        "huerfanas": huerfanas,
        "discrepancias": discrepancias,
        "sin_usar": sin_usar,
        "formato_list": formato_list,
        "tablas_list": tablas_list,
        "figuras_list": figuras_list,
        "gram_list": gram_list,
        "gram_act": gram_act
    }


# -----------------------------------------------------------------------------
# 4. Zona Principal (Carga y Ejecución)
# -----------------------------------------------------------------------------

# Encabezado Principal
st.markdown("""
<div class="righo-header">
    <div class="righo-header-badge">Plataforma Oficial de Diagnóstico</div>
    <h1 class="righo-header-title">RigHo <span style="font-weight: 300; opacity: 0.7;">|</span> Diagnóstico y Auditoría Académica APA 7.ª Ed.</h1>
    <p class="righo-header-subtitle">
        Carga tu borrador o proyecto de tesis en formato <b>.docx</b> para realizar una auditoría automática e inmediata con validación cruzada y evaluación de riesgo de aprobación.
    </p>
</div>
""", unsafe_allow_html=True)

# Subidor de Archivos
subidor_col, accion_col = st.columns([3, 1.2])

with subidor_col:
    archivo_subido = st.file_uploader(
        "Arrastra y suelta tu archivo Word (.docx) aquí o haz clic para explorar:",
        type=["docx"],
        help="Sube un archivo de tesis, proyecto o artículo académico en formato Word (.docx)."
    )

with accion_col:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    boton_auditar = st.button(
        "🔍 Auditar Documento con RigHo",
        type="primary",
        disabled=(archivo_subido is None),
        use_container_width=True
    )

# Procesamiento al presionar el botón
if boton_auditar and archivo_subido is not None:
    tmp_docx_path = None
    tmp_pdf_path = None

    with st.spinner("Analizando normas APA 7, cruce de citas y gramática..."):
        try:
            # 1. Guardar archivo cargado en ruta temporal limpia
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
                tmp_docx.write(archivo_subido.getbuffer())
                tmp_docx_path = tmp_docx.name

            # 2. Generar ruta temporal para el PDF de salida
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name

            # 3. Ejecutar pipeline de análisis modular
            reporte_resultado = ejecutar_pipeline_auditoria(
                ruta_docx=tmp_docx_path,
                analizar_citas=chk_citas,
                analizar_tablas=chk_tablas,
                analizar_formato=chk_formato,
                analizar_gramatica=chk_gramatica
            )
            reporte_resultado["documento"] = archivo_subido.name

            # 4. Generar reporte PDF oficial RigHo
            generar_reporte_pdf(reporte_resultado, tmp_pdf_path)

            # 5. Cargar bytes del PDF a memoria
            with open(tmp_pdf_path, "rb") as f_pdf:
                pdf_bytes = f_pdf.read()

            # 6. Almacenar resultados en session_state para persistencia
            st.session_state["reporte_actual"] = reporte_resultado
            st.session_state["pdf_bytes"] = pdf_bytes
            st.session_state["nombre_archivo"] = archivo_subido.name
            st.toast("¡Auditoría completada exitosamente!", icon="✅")

        except Exception as exc:
            st.error(f"❌ Ocurrió un inconveniente durante el análisis: {str(exc)}")
        finally:
            # Manejo limpio y eliminación de archivos temporales
            if tmp_docx_path and os.path.exists(tmp_docx_path):
                try:
                    os.remove(tmp_docx_path)
                except OSError:
                    pass
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except OSError:
                    pass


# -----------------------------------------------------------------------------
# 5. Tablero de Resultados en Pantalla (Dashboard MVP)
# -----------------------------------------------------------------------------
if "reporte_actual" in st.session_state and st.session_state["reporte_actual"]:
    reporte = st.session_state["reporte_actual"]
    stats = calcular_estadisticas_dashboard(reporte)
    sem = stats["sem_info"]

    st.markdown("<hr style='margin: 30px 0 24px 0; border: none; border-top: 1px solid #E2E8F0;'/>", unsafe_allow_html=True)
    st.markdown(f"### 📊 Resultados de la Auditoría: *{st.session_state.get('nombre_archivo', 'Documento')}*")

    # Tarjeta Destacada: Semáforo de Riesgo de Aprobación
    bg_hex = getattr(sem["bg"], "hexval", lambda: "#FFF5F5")() if hasattr(sem["bg"], "hexval") else "#FFF5F5"
    brd_hex = getattr(sem["brd"], "hexval", lambda: "#FC8181")() if hasattr(sem["brd"], "hexval") else "#FC8181"
    txt_hex = sem["txt_color"]

    st.markdown(f"""
    <div style="background-color: {bg_hex}; border: 2px solid {brd_hex}; border-radius: 12px; padding: 22px 26px; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.03);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
            <div style="flex: 1; min-width: 280px;">
                <div style="font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; color: {txt_hex}; opacity: 0.95;">
                    SEMÁFORO DE RIESGO DE APROBACIÓN
                </div>
                <div style="margin: 4px 0 2px 0; color: {txt_hex}; font-size: 1.85rem; font-weight: 800; font-family: 'Outfit', sans-serif;">
                    {sem['emoji']} {sem['label']}
                </div>
                <div style="color: {txt_hex}; font-weight: 600; font-size: 1.05rem;">
                    {sem['sublabel']}
                </div>
            </div>
            <div style="flex: 1.5; min-width: 320px; background: rgba(255, 255, 255, 0.7); padding: 14px 18px; border-radius: 8px; border-left: 4px solid {brd_hex};">
                <div style="font-weight: 700; font-size: 0.88rem; color: #1E293B; margin-bottom: 4px;">Diagnóstico Preliminar:</div>
                <p style="margin: 0; color: #334155; font-size: 0.93rem; line-height: 1.48;">
                    {sem['detalle']}
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Panel de 4 Métricas Principales (st.metric)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="Total Observaciones",
            value=stats["total_observaciones"],
            help="Suma total de hallazgos en citas, formato, figuras, tablas y gramática."
        )
    with m2:
        st.metric(
            label="Citas en Texto",
            value=stats["total_citas"],
            help="Total de citas en texto analizadas en el cuerpo del documento."
        )
    with m3:
        st.metric(
            label="Inconsistencias (Cruce)",
            value=stats["total_inconsistencias"],
            help="Citas huérfanas, discrepancias de año y referencias sin usar."
        )
    with m4:
        st.metric(
            label="Hallazgos Gramaticales",
            value=stats["total_gram"],
            help="Faltas ortográficas o sintácticas detectadas por el motor de gramática."
        )

    # Botón de Descarga del Informe PDF
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    if "pdf_bytes" in st.session_state and st.session_state["pdf_bytes"]:
        desc_col1, desc_col2 = st.columns([1.5, 1])
        with desc_col1:
            st.download_button(
                label="📥 Descargar Informe Completo en PDF (reporte_diagnostico_righo.pdf)",
                data=st.session_state["pdf_bytes"],
                file_name="reporte_diagnostico_righo.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with desc_col2:
            st.markdown("""
            <div style="background: #E6F7FF; border: 1px solid #BEE3F8; border-radius: 8px; padding: 10px 14px; font-size: 0.84rem; color: #0C5460;">
                💡 <b>Tip RigHo:</b> El PDF incluye foliación 'Página X de Y', membrete institucional y detalles listos para remitir a tu asesor.
            </div>
            """, unsafe_allow_html=True)

    # Desglose Rápido en Pestañas (Exploración en Pantalla)
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 🔍 Desglose Detallado de Hallazgos")

    tab_cruce, tab_formato, tab_tablas, tab_gram = st.tabs([
        "🔗 Cruce Citas vs. Referencias",
        "📐 Formato e Interlineado",
        "📊 Tablas y Figuras",
        "✍️ Gramática y Sintaxis"
    ])

    with tab_cruce:
        if stats["total_inconsistencias"] == 0:
            st.success("✅ ¡Excelente! No se detectaron inconsistencias en el cruce de citas y referencias.")
        else:
            if stats["huerfanas"]:
                st.markdown(f"**🔴 Citas Huérfanas ({len(stats['huerfanas'])})** — *Aparecen en el texto pero no están en la lista de referencias:*")
                for h in stats["huerfanas"]:
                    st.error(f"**Cita:** {h.get('cita')}  \n{h.get('mensaje')}")

            if stats["discrepancias"]:
                st.markdown(f"**🟡 Discordancias de Año ({len(stats['discrepancias'])})** — *El autor coincide pero difiere en el año:*")
                for d in stats["discrepancias"]:
                    st.warning(f"**Autor:** {d.get('autor')}  \n{d.get('mensaje')}")

            if stats["sin_usar"]:
                st.markdown(f"**⚪ Referencias sin Citar ({len(stats['sin_usar'])})** — *Están en la bibliografía pero no fueron citadas en el texto:*")
                for s in stats["sin_usar"][:10]:
                    st.info(f"**Referencia:** {s.get('autor')} ({s.get('anio')})  \n{s.get('mensaje')}")
                if len(stats["sin_usar"]) > 10:
                    st.caption(f"*Mostrando las 10 primeras de {len(stats['sin_usar'])} referencias sin citar. Descarga el PDF para la lista completa.*")

    with tab_formato:
        if not stats["formato_list"]:
            st.success("✅ El documento cumple con los estándares generales de formato APA 7.")
        else:
            st.markdown(f"Se detectaron **{len(stats['formato_list'])}** observaciones de formato general:")
            for fmt in stats["formato_list"][:15]:
                st.warning(f"**{fmt.get('tipo', '').capitalize()}:** {fmt.get('mensaje')}  \n*Extracto:* \"{fmt.get('parrafo', 'N/A')}\"")
            if len(stats["formato_list"]) > 15:
                st.caption(f"*Mostrando 15 observaciones representativas de {len(stats['formato_list'])} totales. Consulta el PDF completo.*")

    with tab_tablas:
        tablas_err = [t for t in stats["tablas_list"] if t.get("errores")]
        figuras_err = [f for f in stats["figuras_list"] if f.get("errores")]
        if not tablas_err and not figuras_err:
            st.success("✅ Todas las tablas y figuras analizadas cumplen con los requisitos de APA 7.")
        else:
            if tablas_err:
                st.markdown(f"**Tablas con observaciones ({len(tablas_err)}):**")
                for t in tablas_err:
                    msgs = " · ".join([e.get("mensaje", "") for e in t.get("errores", [])])
                    st.warning(f"**{t.get('etiqueta', 'Tabla')}:** {msgs}")
            if figuras_err:
                st.markdown(f"**Figuras con observaciones ({len(figuras_err)}):**")
                for f in figuras_err:
                    msgs = " · ".join([e.get("mensaje", "") for e in f.get("errores", [])])
                    st.warning(f"**{f.get('etiqueta', 'Figura')}:** {msgs}")

    with tab_gram:
        if not stats["gram_act"]:
            st.info("ℹ️ El análisis ortográfico y gramatical no fue activado para esta auditoría.")
        elif isinstance(stats["total_gram"], int) and stats["total_gram"] == 0:
            st.success("✅ No se detectaron faltas ortográficas ni sintácticas graves.")
        elif stats["gram_list"] and "error" in stats["gram_list"][0]:
            st.warning(f"⚠️ {stats['gram_list'][0]['error']}")
        else:
            st.markdown(f"Se detectaron **{len(stats['gram_list'])}** posibles faltas ortográficas o sintácticas:")
            for g in stats["gram_list"][:15]:
                sugs = ", ".join(g.get("sugerencias", []))
                sug_txt = f" (Sugerencias: *{sugs}*)" if sugs else ""
                st.error(f"**Error:** `{g.get('fragmento_error')}`{sug_txt}  \n{g.get('mensaje')}  \n*Contexto:* \"{g.get('parrafo_extracto')}\"")
            if len(stats["gram_list"]) > 15:
                st.caption(f"*Mostrando 15 de {len(stats['gram_list'])} hallazgos gramaticales. Revisa el PDF para el reporte completo.*")

else:
    # Estado inicial: Bienvenida y guía de uso
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    info_col1, info_col2, info_col3 = st.columns(3)

    with info_col1:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-size: 1.4rem; margin-bottom: 6px;">🔗</div>
            <div style="font-weight: 700; color: #0F2537; font-size: 0.98rem; margin-bottom: 4px;">Cruce Citas vs. Referencias</div>
            <div style="font-size: 0.88rem; color: #64748B; line-height: 1.4;">
                Detección del 100% de citas huérfanas, discordancias en años de publicación y referencias no citadas.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with info_col2:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-size: 1.4rem; margin-bottom: 6px;">📐</div>
            <div style="font-weight: 700; color: #0F2537; font-size: 0.98rem; margin-bottom: 4px;">Formato, Títulos y Tablas</div>
            <div style="font-size: 0.88rem; color: #64748B; line-height: 1.4;">
                Auditoría estricta de sangría francesa, márgenes de 2.54 cm, interlineado doble y formato de tablas y figuras.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with info_col3:
        st.markdown("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
            <div style="font-size: 1.4rem; margin-bottom: 6px;">📄</div>
            <div style="font-weight: 700; color: #0F2537; font-size: 0.98rem; margin-bottom: 4px;">Informe Ejecutivo PDF</div>
            <div style="font-size: 0.88rem; color: #64748B; line-height: 1.4;">
                Emisión instantánea de informe técnico foliado con branding institucional y clasificación de riesgo para tu jurado.
            </div>
        </div>
        """, unsafe_allow_html=True)
