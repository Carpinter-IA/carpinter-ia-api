from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pypdf import PdfReader, PdfWriter
from openpyxl import Workbook
from io import BytesIO
import os
import base64
from PIL import Image

app = Flask(__name__)
CORS(app)

# ===============================
# RUTA DEL PDF MAESTRO (FINAL)
# ===============================
PDF_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "Carpinter-IA_Despiece.pdf"  # <<--- ESTE ES EL PDF QUE ESTAMOS USANDO
)

# ===============================
# HEALTH CHECK
# ===============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ===============================
# ENDPOINT PRINCIPAL /ocr
# ===============================
@app.route("/ocr", methods=["POST"])
def ocr_process():
    try:
        # ================
        # 1. Recibir IMAGEN
        # ================
        if "file" not in request.files:
            return jsonify({"error": "No se recibió ninguna imagen"}), 400

        file = request.files["file"]
        img = Image.open(file.stream)

        # ================
        # 2. Recibir datos del formulario
        # ================
        material = request.form.get("material", "")
        espesor = request.form.get("espesor", "")
        cliente = request.form.get("cliente", "")

        # ================
        # 3. Datos de prueba (sin OCR real)
        # ================
        piezas = [
            {"ref": "Lateral izquierdo", "largo": "800", "ancho": "400", "espesor": espesor, "cantidad": "1", "L1": "1", "L2": "0", "A1": "0", "A2": "0"},
            {"ref": "Lateral derecho", "largo": "800", "ancho": "400", "espesor": espesor, "cantidad": "1", "L1": "1", "L2": "0", "A1": "0", "A2": "0"},
            {"ref": "Base", "largo": "700", "ancho": "400", "espesor": espesor, "cantidad": "1", "L1": "0", "L2": "0", "A1": "0", "A2": "0"},
        ]

        # ================
        # 4. Rellenar PDF MAESTRO
        # ================
        reader = PdfReader(PDF_TEMPLATE_PATH)
        writer = PdfWriter()

        page = reader.pages[0]

        # FORM FIELDS (exactos del PDF maestro)
        writer.add_page(page)
        writer.update_page_form_field_values(writer.pages[0], {
            "NOMBRE": cliente,
            "MATERIAL": material,
            "ESPESOR": espesor
        })

        # -------------------------
        # Rellenar las piezas
        # -------------------------
        for i, p in enumerate(piezas):
            idx = str(i + 1)
            writer.update_page_form_field_values(writer.pages[0], {
                f"ref_{idx}": p["ref"],
                f"largo_{idx}": p["largo"],
                f"ancho_{idx}": p["ancho"],
                f"espesor_{idx}": p["espesor"],
                f"cantidad_{idx}": p["cantidad"],
                f"L1_{idx}": p["L1"],
                f"L2_{idx}": p["L2"],
                f"A1_{idx}": p["A1"],
                f"A2_{idx}": p["A2"]
            })

        # Guardar PDF en memoria
        pdf_output = BytesIO()
        writer.write(pdf_output)
        pdf_output.seek(0)

        # ================
        # 5. Exportar Excel
        # ================
        wb = Workbook()
        ws = wb.active
        ws.append(["REF", "LARGO", "ANCHO", "ESPESOR", "CANTIDAD", "L1", "L2", "A1", "A2"])
        for p in piezas:
            ws.append([p["ref"], p["largo"], p["ancho"], p["espesor"], p["cantidad"], p["L1"], p["L2"], p["A1"], p["A2"]])

        excel_output = BytesIO()
        wb.save(excel_output)
        excel_output.seek(0)

        # ================
        # 6. Convertir PDF → base64
        # ================
        pdf_b64 = base64.b64encode(pdf_output.getvalue()).decode("utf-8")

        return jsonify({
            "status": "ok",
            "pdf_base64": pdf_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===============================
# MAIN LOCAL
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
