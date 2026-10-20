import docx
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "tests/prueba.docx"
documento = docx.Document(ruta)

for parrafo in documento.paragraphs:
    if parrafo.text.strip() == "Tabla 3":
        print("Tamaños en los runs:", [r.font.size for r in parrafo.runs])
        estilo = parrafo.style
        nivel = 0
        while estilo is not None:
            print(f"Nivel {nivel}: estilo='{estilo.name}', tamano={estilo.font.size}")
            estilo = estilo.base_style
            nivel += 1
        break