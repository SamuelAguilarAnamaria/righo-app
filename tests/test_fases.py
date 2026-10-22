import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engines.referencias import parsear_referencia, es_autor_corporativo
from cli import evaluar_coincidencia, primer_apellido_normalizado
from app.extraction.docx_parser import es_etiqueta_elemento_visual
from app.engines.titulos import revisar_titulos

# 1. Test referencias: Corporate author & '(s. f.)'
ref_corp = "Ministerio de Salud del Perú (2022). Plan Estratégico. https://minsa.gob.pe"
parsed_corp = parsear_referencia(ref_corp)
assert parsed_corp["anio"] == "2022", f"Expected 2022, got {parsed_corp['anio']}"
errores_corp = [e["tipo"] for e in parsed_corp["errores"]]
assert "ref_autor_sin_iniciales" not in errores_corp, f"Corporate author got sin_iniciales error: {errores_corp}"

ref_sf = "García, J. (s. f.). Documento sin fecha. Editorial."
parsed_sf = parsear_referencia(ref_sf)
assert parsed_sf["anio"].strip() == "s. f.", f"Expected 's. f.', got '{parsed_sf['anio']}'"
errores_sf = [e["tipo"] for e in parsed_sf["errores"]]
assert "ref_sin_anio" not in errores_sf, f"s. f. flagged as sin_anio: {errores_sf}"

# 2. Test cli: difflib / primer apellido
assert primer_apellido_normalizado("Fernández-Berrocal") == "fernandez-berrocal"
assert primer_apellido_normalizado("Fernández, Baptista & Hernández") == "fernandez"

cita_fb = {"autor": "Fernández-Berrocal", "anio": "2018"}
ref_f = {"autor": "Fernández, Baptista & Hernández", "anio": "2018"}
res_fb = evaluar_coincidencia(cita_fb, ref_f)
assert res_fb == "NINGUNA", f"Expected NINGUNA, got {res_fb}"

cita_f = {"autor": "Fernández", "anio": "2018"}
ref_f2 = {"autor": "Fernández, R.", "anio": "2018"}
assert evaluar_coincidencia(cita_f, ref_f2) == "EXACTA"

# 3. Test docx_parser labels
assert es_etiqueta_elemento_visual("Tabla 1") is True
assert es_etiqueta_elemento_visual("Tabla 12  ") is True
assert es_etiqueta_elemento_visual("Figura 3") is True
assert es_etiqueta_elemento_visual("En la siguiente Tabla 1 se describe...") is False

# 4. Test titulos
dummy_data = {
    "parrafos": [
        {"texto": "1. Introducción", "estilo": "Heading 1", "alineacion": "LEFT", "sangria_primera_linea_cm": None},
        {"texto": "Título Centrado Válido", "estilo": "Heading 1", "alineacion": "CENTER", "sangria_primera_linea_cm": None},
    ]
}
res_titulos = revisar_titulos(dummy_data)
assert len(res_titulos) == 2
assert len(res_titulos[0]["errores"]) > 0  # Nivel 1 debe estar centrado

# 5. Test gramatica autodetección inglés/español
from app.engines.gramatica import revisar_gramatica, cerrar_tool
dummy_gram = {
    "parrafos": [
        {"texto": "Yo tiene hambre y el perro estan durmiendo en la sala."},
        {"texto": "He go to school yesterday and she have two dogs at home."}
    ]
}
res_gram = revisar_gramatica(dummy_gram)
cerrar_tool()
# 6. Test citas con acentos y formatos especiales (Alcóser, 2019)
from app.engines.citas import extraer_citas_parrafo, procesar_citas, REGEX_CITAS_TEXTO
from app.engines.referencias import REGEX_ANIO_REFERENCIA

p_acento = "Estudios previos señalan que (Alcóser, 2019) y también (Alcóser et al., 2019, p. 45) confirmaron los datos."
citas_p = extraer_citas_parrafo(p_acento)
assert len(citas_p) == 2, f"Expected 2 citations with accents, got {len(citas_p)}"
assert citas_p[0]["autores_raw"] == "Alcóser"
assert citas_p[0]["anio"] == "2019"
assert citas_p[1]["autores_raw"] == "Alcóser et al."

# Test REGEX_CITAS_TEXTO directly
m_directo = REGEX_CITAS_TEXTO.search("(Alcóser, 2019)")
assert m_directo is not None
assert m_directo.group(1).strip() == "Alcóser"
assert m_directo.group(2).strip() == "2019"

# 7. Test fechas extendidas en referencias (24 de Noviembre de 2020), (julio de 2008)
ref_ext1 = "Ministerio de Salud. (24 de Noviembre de 2020). Protocolo sanitario. https://minsa.gob.pe"
parsed_ext1 = parsear_referencia(ref_ext1)
assert parsed_ext1["anio"] == "2020", f"Expected 2020, got {parsed_ext1['anio']}"
assert not any(e["tipo"] == "ref_sin_anio" for e in parsed_ext1["errores"])

ref_ext2 = "Gómez, P. (julio de 2008). Evaluación educativa. Revista."
parsed_ext2 = parsear_referencia(ref_ext2)
assert parsed_ext2["anio"] == "2008", f"Expected 2008, got {parsed_ext2['anio']}"
assert not any(e["tipo"] == "ref_sin_anio" for e in parsed_ext2["errores"])

# 8. Test coincidencia cruzada con acentos y fechas extendidas
cita_alcoser = {"autor": "Alcóser", "anio": "2019"}
ref_alcoser = {"autor": "Alcóser, J.", "anio": "2019"}
assert evaluar_coincidencia(cita_alcoser, ref_alcoser) == "EXACTA"

cita_minsa = {"autor": "Ministerio de Salud", "anio": "2020"}
assert evaluar_coincidencia(cita_minsa, parsed_ext1) == "EXACTA"

# 9. Test citas en tablas (doc.tables)
datos_con_tabla = {
    "parrafos": [
        {"texto": "Párrafo introductorio de cuerpo.", "en_tabla": False},
        {"texto": "Dato según (Alcóser, 2019) dentro de celda.", "en_tabla": True}
    ],
    "tablas": [
        {"nota_texto": "Nota. Adaptado de Pérez (2018).", "titulo_texto": "Tabla 1"}
    ]
}
citas_totales = procesar_citas(datos_con_tabla)
assert any(c["autores_raw"] == "Alcóser" for c in citas_totales), "Citation in table was not found!"
assert any(c["autores_raw"] == "Pérez" for c in citas_totales), "Citation in table note was not found!"

# 10. Test conversiones numéricas seguras (safe_int / safe_float) y valores float en XML
from app.extraction.docx_parser import safe_int, safe_float
import docx.oxml.simpletypes as docx_st
from app.engines.formato import revisar_formato

assert safe_int("164.00000000000006") == 164
assert safe_int("24") == 24
assert safe_int(24.8) == 24
assert safe_int("invalido", default=0) == 0
assert safe_int(None, default=-1) == -1

assert safe_float("164.00000000000006") == 164.00000000000006
assert safe_float("12.5") == 12.5
assert safe_float(None, default=0.0) == 0.0

# Verificar que python-docx maneja strings flotantes sin lanzar ValueError
pt_res = docx_st.ST_HpsMeasure.convert_from_xml("164.00000000000006")
assert pt_res is not None

# Test revisión de formato con valores decimales flotantes en cadenas
datos_float_str = {
    "margenes": {"superior": "2.54", "inferior": 2.54, "izquierdo": 2.54, "derecho": 2.54},
    "parrafos": [
        {
            "texto": "Texto de prueba con interlineado y fuente segura.",
            "fuente": "Arial",
            "tamano_fuente_pt": "12.00000000000001",
            "interlineado": "2.0000000000000004",
            "alineacion": "JUSTIFY",
            "sangria_primera_linea_cm": "1.2700000000000002",
            "sangria_izquierda_cm": None,
            "en_tabla": False,
            "en_portada": False,
        }
    ]
}
hallazgos_format = revisar_formato(datos_float_str)
assert len(hallazgos_format) == 0, f"Expected 0 errors with valid float formatted strings, got {hallazgos_format}"

# 11. Test optimizaciones de memoria en gramática (filtrado de vacíos y chunking > 100 párrafos)
from app.engines.gramatica import get_language_tool

class MockLanguageTool:
    def __init__(self):
        self.checked_texts = []
    def check(self, text):
        self.checked_texts.append(text)
        return []

mock_tool = MockLanguageTool()

# Documento con párrafos vacíos, solo espacios y más de 100 párrafos
parrafos_test = [{"texto": ""}, {"texto": "   \n\t  "}]
for i in range(120):
    parrafos_test.append({"texto": f"Este es el párrafo de prueba número {i} con contenido académico válido para auditoría."})

datos_grandes = {"parrafos": parrafos_test}
errores_chunk = revisar_gramatica(datos_grandes, tool=mock_tool)
assert isinstance(errores_chunk, list)
# Asegurar que se filtraron los 2 párrafos vacíos
assert len(mock_tool.checked_texts) == 120
assert "" not in mock_tool.checked_texts
assert "   \n\t  " not in mock_tool.checked_texts

print("TODOS LOS TESTS DE VALIDACIÓN PASARON EXITOSAMENTE (100% OK).")



