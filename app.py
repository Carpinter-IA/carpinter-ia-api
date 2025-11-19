import os
import base64
from io import BytesIO

from flask import Flask, request, jsonify
from flask_cors import CORS

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from openpyxl import Workbook


app = Flask(__name__)
CORS(app)

# ============================
#   RUTA DEL PDF MAESTRO
# ============================
# OJO: el nombre debe coincidir EXACTAMENTE con el archivo que tienes en GitHub.
PDF_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "Carpinter-IA_Despiece.pdf"
)


# ============================
#   ENDPOINT DE SALUD
# ============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ============================
#   ENDPOINT PRINCIPAL /ocr
#   - Recibe: multipart/form-data
#     * file  -> imagen del despiece
#     * material (opcional)
#     * espesor (opcional)
#     * cliente (opcional)
# ============================
@app.route("/ocr", methods=["POST"])
def ocr():
    try:
        # --------------------------------
        # 1. Comprobar que llega el archivo
        # --------------------------------
        if "file" not in request.files:
            return jsonify({"error": "No se encontró el archivo 'file' en la petición"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "El archivo está vacío"}), 400

        # Solo validamos que la imagen se pueda abrir (no la usamos aún para OCR real)
        try:
            image = Image.open(file.stream)
            image.verify()  # comprueba que es una imagen válida
        except Exception:
            return jsonify({"error": "El archivo enviado no es una imagen válida"}), 400

        # --------------------------------
        # 2. Campos adicionales del formulario
        # --------------------------------
        material = request.form.get("material", "").strip()
        espesor = request.form.get("espesor", "").strip()
        cliente = request.form.get("cliente", "").strip()

        # --------------------------------
        # 3. Piezas de ejemplo (hasta conectar OCR real)
        #    Aquí luego engancharemos ocr_rayas_tesseract.py
        # --------------------------------
        piezas = [
            {"nombre": "Lateral izquierdo", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Lateral derecho", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Base", "medidas": "700 x 400", "cantidad": 1},
        ]

        # ============================
        #   GENERAR EXCEL (DESPIECE)
        # ============================
        excel_buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Despiece"

        # Cabeceras
        ws.append(["Pieza", "Medidas", "Cantidad"])
        # Datos
        for p in piezas:
            ws.append([p["nombre"], p["medidas"], p["cantidad"]])

        wb.save(excel_buffer)
        excel_buffer.seek(0)

        # ============================
        #   GENERAR PDF DESDE PLANTILLA
        # ============================
        if not os.path.exists(PDF_TEMPLATE_PATH):
            return jsonify({
                "error": f"No se ha encontrado la plantilla PDF en {PDF_TEMPLATE_PATH}"
            }), 500

        # Cargamos la plantilla
        template_reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()
        base_page = template_reader.pages[0]

        # Creamos una capa con ReportLab
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 10)

        # Coordenadas base (puedes ajustarlas más adelante)
        x_text = 50
        y_text = 760

        # Encabezado con datos del proyecto
        if cliente:
            can.drawString(x_text, y_text, f"Cliente / proyecto: {cliente}")
            y_text -= 15
        if material:
            can.drawString(x_text, y_text, f"Material: {material}")
            y_text -= 15
        if espesor:
            can.drawString(x_text, y_text, f"Espesor: {espesor}")
            y_text -= 25
        else:
            y_text -= 10

        # Título de la tabla
        can.drawString(x_text, y_text, "Despiece generado (versión demo sin OCR real):")
        y_text -= 20

        # Dibujar cada pieza
        for p in piezas:
            linea = f"- {p['nombre']} | {p['medidas']} | Cant: {p['cantidad']}"
            can.drawString(x_text, y_text, linea)
            y_text -= 15
            if y_text < 80:  # por si se llena la página
                break

        can.save()
        packet.seek(0)

        overlay_reader = PdfReader(packet)
        overlay_page = overlay_reader.pages[0]

        # Fusionamos la capa de texto con la plantilla
        base_page.merge_page(overlay_page)
        writer.add_page(base_page)

        pdf_buffer = BytesIO()
        writer.write(pdf_buffer)
        pdf_buffer.seek(0)

        # ============================
        #   CODIFICAR EN BASE64
        # ============================
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode("utf-8")
        excel_base64 = base64.b64encode(excel_buffer.read()).decode("utf-8")

        # Respuesta final
        return jsonify({
            "status": "ok",
            "mensaje": "Despiece generado correctamente (modo demo).",
            "piezas": piezas,
            "pdf_base64": pdf_base64,
            "excel_base64": excel_base64,
        }), 200

    except Exception as e:
        # Para depurar mejor si algo falla
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Solo para pruebas locales, en Render se usa gunicorn con el PORT que ellos ponen
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
