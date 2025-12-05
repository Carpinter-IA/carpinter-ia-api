# -*- coding: utf-8 -*-
import os
import json
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from ocr_rayas_tesseract import run_ocr_and_get_pieces  # usa tu función OCR

app = Flask(__name__)
CORS(app)

# ------------------------------------------
#   VARIABLE GLOBAL PARA GUARDAR RESULTADOS
# ------------------------------------------
ULTIMO_RESULTADO = {
    "piezas": [],
    "image_width": None,
    "image_height": None,
    "meta": {}
}

DEBUG_OVERLAY_PATH = "/tmp/debug_overlay.png"


# ------------------------------------------
#      ENDPOINT HEALTH CHECK PARA RENDER
# ------------------------------------------
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


# ------------------------------------------
#   ENDPOINT PRINCIPAL /OCR
# ------------------------------------------
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "Falta el archivo 'file'"}), 400

    file = request.files["file"]
    material = request.form.get("material", "")
    espesor = request.form.get("espesor", "")
    cliente = request.form.get("cliente", "")

    # guardar archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        temp_path = tmp.name
        file.save(temp_path)

    # ejecutar OCR
    try:
        piezas, w, h = run_ocr_and_get_pieces(temp_path, debug_overlay=DEBUG_OVERLAY_PATH)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # guardar resultado global
    ULTIMO_RESULTADO["piezas"] = piezas
    ULTIMO_RESULTADO["image_width"] = w
    ULTIMO_RESULTADO["image_height"] = h
    ULTIMO_RESULTADO["meta"] = {
        "material": material,
        "espesor": espesor,
        "cliente": cliente,
        "image_path": temp_path
    }

    # generar PDF desde piezas
    try:
        from generar_pdf import crear_pdf_desde_piezas
        output_pdf = "/tmp/output_from_json.pdf"
        crear_pdf_desde_piezas(piezas, output_pdf, material=material, espesor=espesor, cliente=cliente)
    except Exception as e:
        return jsonify({"error": f"Error generando PDF: {e}"}), 500

    return send_file(output_pdf, mimetype="application/pdf")


# ------------------------------------------
#      ENDPOINT: ÚLTIMO RESULTADO JSON
# ------------------------------------------
@app.route("/last_result.json", methods=["GET"])
def last_json():
    return jsonify(ULTIMO_RESULTADO)


# ------------------------------------------
#      ENDPOINT: OVERLAY DEBUG
# ------------------------------------------
@app.route("/debug_overlay.png", methods=["GET"])
def overlay():
    if not os.path.exists(DEBUG_OVERLAY_PATH):
        return jsonify({"error": "Overlay no generado aún"}), 404
    return send_file(DEBUG_OVERLAY_PATH, mimetype="image/png")


# ------------------------------------------
#      EJECUCIÓN LOCAL
# ------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
