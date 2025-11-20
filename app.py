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

        # Validar que es imagen
        try:
            image = Image.open(file.stream)
            image.verify()
        except Exception:
            return jsonify({"error": "El archivo enviado no es una imagen válida"}), 400

        # --------------------------------
        # 2. Campos adicionales
        # --------------------------------
        material = request.form.get("material", "").strip()
        espesor = request.form.get("espesor", "").strip()
        cliente = request.form.get("cliente", "").strip()

        # --------------------------------
        # 3. Piezas DEMO (luego irá el OCR real)
        # --------------------------------
        piezas = [
            {"nombre": "Lateral izquierdo", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Lateral derecho", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Base", "medidas": "700 x 400", "cantidad": 1},
        ]

        # ============================
        #   EXCEL DE DESPIECE
        # ============================
        excel_buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Despiece"

        ws.append(["Pieza", "Medidas", "Cantidad"])
        for p in piezas:
            ws.append([p["nombre"], p["medidas"], p["cantidad"]])

        wb.save(excel_buffer)
        excel_buffer.seek(0)

        # ============================
        #   PDF DESDE PLANTILLA
        # ============================
        if not os.path.exists(PDF_TEMPLATE_PATH):
            return jsonify({
                "error": f"No se ha encontrado la plantilla PDF en {PDF_TEMPLATE_PATH}"
            }), 500

        template_reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()
        base_page = template_reader.pages[0]

        # Capa nueva con ReportLab
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 10)

        # ---- CABECERA (debajo del logo, encima de “Datos del cliente”) ----
        header_x = 50
        header_y = 780

        y = header_y
        if cliente:
            can.drawString(header_x, y, f"Cliente / proyecto: {cliente}")
            y -= 15
        if material:
            can.drawString(header_x, y, f"Material: {material}")
            y -= 15
        if espesor:
            can.drawString(header_x, y, f"Espesor: {espesor}")
            y -= 15

        # ---- TEXTO DE DESPIECE (lo bajamos, para que no tape “Datos del cliente”) ----
        x_text = 50
        # Esta altura la hemos elegido para que quede entre “Datos del cliente”
        # y “Piezas solicitadas”. Si se solapa un poco, luego ajustamos unos puntos.
        y_text = 560

        can.drawString(x_text, y_text, "Despiece generado (versión demo sin OCR real):")
        y_text -= 20

        for p in piezas:
            linea = f"- {p['nombre']} | {p['medidas']} | Cant: {p['cantidad']}"
            can.drawString(x_text, y_text, linea)
            y_text -= 15
            if y_text < 80:  # por si se llena demasiado
                break

        can.save()
        packet.seek(0)

        overlay_reader = PdfReader(packet)
        overlay_page = overlay_reader.pages[0]

        base_page.merge_page(overlay_page)
        writer.add_page(base_page)

        pdf_buffer = BytesIO()
        writer.write(pdf_buffer)
        pdf_buffer.seek(0)

        # ============================
        #   BASE64
        # ============================
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode("utf-8")
        excel_base64 = base64.b64encode(excel_buffer.read()).decode("utf-8")

        return jsonify({
            "status": "ok",
            "mensaje": "Despiece generado correctamente (modo demo).",
            "piezas": piezas,
            "pdf_base64": pdf_base64,
            "excel_base64": excel_base64,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
