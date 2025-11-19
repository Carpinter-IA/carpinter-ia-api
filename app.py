import os
import base64
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from pypdf import PdfReader, PdfWriter
from openpyxl import Workbook
from io import BytesIO

app = Flask(__name__)
CORS(app)

# ============================
#   RUTA DEL PDF MAESTRO
# ============================
PDF_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), 
    "Carpinter-IA_Despiece.pdf"
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ocr", methods=["POST"])
def ocr_process():
    try:
        # ---------------------------
        # 1. Validar archivo enviado
        # ---------------------------
        if "file" not in request.files:
            return jsonify({"error": "No se envió archivo 'file'"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Archivo vacío"}), 400

        image = Image.open(file.stream)

        # ---------------------------------------------
        #   Simulamos OCR (hasta que lo activemos real)
        # ---------------------------------------------
        piezas = [
            {"nombre": "Lateral Izquierdo", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Lateral Derecho", "medidas": "800 x 400", "cantidad": 1},
            {"nombre": "Base", "medidas": "700 x 400", "cantidad": 1},
        ]

        # ============================
        #   GENERAR EXCEL DESPIECE
        # ============================
        excel_output = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Despiece"

        ws.append(["Pieza", "Medidas", "Cantidad"])
        for p in piezas:
            ws.append([p["nombre"], p["medidas"], p["cantidad"]])

        wb.save(excel_output)
        excel_output.seek(0)

        # ============================
        #   GENERAR PDF DESDE PLANTILLA
        # ============================
        if not os.path.exists(PDF_TEMPLATE_PATH):
            return jsonify({"error": f"NO se encontró la plantilla: {PDF_TEMPLATE_PATH}"}), 500

        print("📄 Usando plantilla PDF:", PDF_TEMPLATE_PATH)

        reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()

        page = reader.pages[0]

        # Texto superpuesto
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 10)

        y = 730
        for p in piezas:
            can.drawString(50, y, f"{p['nombre']} — {p['medidas']} — Cant: {p['cantidad']}")
            y -= 15

        can.save()
        packet.seek(0)

        # Fusionar
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

        final_pdf = BytesIO()
        writer.write(final_pdf)
        final_pdf.seek(0)

        # ============================
        # RESPUESTA EN BASE64
        # ============================
        pdf_b64 = base64.b64encode(final_pdf.read()).decode("utf-8")
        excel_b64 = base64.b64encode(excel_output.read()).decode("utf-8")

        return jsonify({
            "status": "ok",
            "pdf": pdf_b64,
            "excel": excel_b64,
            "piezas": piezas
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
