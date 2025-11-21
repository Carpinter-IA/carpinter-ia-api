import os
from io import BytesIO

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

# Usamos la librería que tienes en requirements.txt
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

# -------------------------------------------------------------------
# CONFIGURACIÓN BÁSICA
# -------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# Ruta del PDF maestro (debe llamarse así en el servidor)
PDF_TEMPLATE_NAME = "Carpinter-IA_Despiece.pdf"
PDF_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), PDF_TEMPLATE_NAME)


# -------------------------------------------------------------------
# ENDPOINT DE SALUD
# -------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# -------------------------------------------------------------------
# FUNCIÓN PARA GENERAR EL PDF DE DESPIECE
# -------------------------------------------------------------------

def generar_pdf_despiece(material: str, espesor: str, cliente: str) -> bytes:
    """
    Genera un PDF a partir del PDF maestro, escribiendo encima
    un despiece DEMO sin usar campos de formulario (sin AcroForm).
    Devuelve los bytes del PDF final.
    """

    if not os.path.exists(PDF_TEMPLATE_PATH):
        raise FileNotFoundError(f"No se encuentra la plantilla: {PDF_TEMPLATE_PATH}")

    # 1) Leemos la plantilla
    reader = PdfReader(PDF_TEMPLATE_PATH)
    base_page = reader.pages[0]

    # Dimensiones de la página para colocar el texto
    width = float(base_page.mediabox.width)
    height = float(base_page.mediabox.height)

    # 2) Creamos un PDF "overlay" con reportlab donde escribimos el texto
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))

    # Fuente pequeña para que quepa bien
    can.setFont("Helvetica", 8)

    # ----------------------------------------------------------------
    # CABECERA DE TEXTO DEL DESPIECE (debajo de “Piezas solicitadas”)
    # ----------------------------------------------------------------
    # Coordenadas aproximadas (puedes afinar si quieres)
    # (0,0) está abajo a la izquierda.
    y_inicio = height - 300  # más o menos donde empieza la tabla
    x_texto = 60

    linea_intro = "Despiece generado (versión demo sin OCR real):"
    can.drawString(x_texto, y_inicio, linea_intro)

    y = y_inicio - 12

    # DEMO de piezas (puedes cambiar los textos cuando quieras)
    piezas_demo = [
        {"nombre": "Lateral izquierdo", "largo": 800, "ancho": 400, "cant": 1},
        {"nombre": "Lateral derecho", "largo": 800, "ancho": 400, "cant": 1},
        {"nombre": "Base", "largo": 700, "ancho": 400, "cant": 1},
    ]

    for pieza in piezas_demo:
        linea = (
            f"- {pieza['nombre']} | "
            f"{pieza['largo']} x {pieza['ancho']} | "
            f"{espesor} | Cant: {pieza['cant']}"
        )
        can.drawString(x_texto + 10, y, linea)
        y -= 12

    # Si quieres también podemos escribir el material, espesor y cliente
    # en algún punto de la hoja (de momento lo dejamos solo en la intro).
    # Ejemplo (descomenta si lo quieres):
    #
    # can.setFont("Helvetica-Bold", 9)
    # can.drawString(60, height - 260, f"Cliente / proyecto: {cliente}")
    # can.drawString(60, height - 272, f"Material: {material}")
    # can.drawString(60, height - 284, f"Espesor: {espesor}")

    can.save()
    packet.seek(0)

    overlay_reader = PdfReader(packet)

    # 3) Fusionamos la plantilla con el overlay
    writer = PdfWriter()
    base_page.merge_page(overlay_reader.pages[0])
    writer.add_page(base_page)

    # 4) Guardamos en memoria
    output_pdf = BytesIO()
    writer.write(output_pdf)
    output_pdf.seek(0)

    return output_pdf.read()


# -------------------------------------------------------------------
# ENDPOINT PRINCIPAL /ocr
# -------------------------------------------------------------------

@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    """
    Recibe:
      - file: imagen del despiece (no la procesamos en esta DEMO)
      - material: texto libre
      - espesor: texto libre
      - cliente: texto libre

    Devuelve:
      - Un PDF (application/pdf) generado a partir de la plantilla.
    """

    try:
        # Imagen (por ahora no usamos OCR en esta versión demo)
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "Falta el archivo 'file' en el formulario"}), 400

        # Campos de texto del formulario
        material = request.form.get("material", "").strip() or "Material sin especificar"
        espesor = request.form.get("espesor", "").strip() or "Espesor sin especificar"
        cliente = request.form.get("cliente", "").strip() or "Cliente sin especificar"

        # Generamos el PDF
        pdf_bytes = generar_pdf_despiece(material, espesor, cliente)

        # Devolvemos el PDF directamente
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="Carpinter-IA_Despiece.pdf",
        )

    except Exception as e:
        # Para ver el error en los logs de Render
        print("Error en /ocr:", repr(e))
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------------------------
# MAIN LOCAL (por si quieres probarlo en tu PC)
# -------------------------------------------------------------------

if __name__ == "__main__":
    # Solo para desarrollo local. En Render se lanza con Gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=True)
