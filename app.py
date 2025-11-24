# --- pega este bloque en tu backend Python (ej: app.py) ---
import os
import json
from flask import Flask, request, send_file, jsonify, make_response

app = Flask(__name__)

DEBUG_JSON_PATH = "/tmp/carpinteria_last_result.json"  # o usa una ruta en tu proyecto

def save_debug_json(piezas, image_width, image_height, meta=None):
    """
    Guarda un JSON con la última detección para depuración.
    'piezas' debe ser lista de objetos con keys: id, nombre, x, y, w, h, texto (px coords).
    """
    payload = {
        "piezas": piezas,
        "image_width": image_width,
        "image_height": image_height,
    }
    if meta:
        payload["meta"] = meta
    with open(DEBUG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    app.logger.info(f"Debug JSON saved to {DEBUG_JSON_PATH}")

@app.route("/last_result.json", methods=["GET"])
def last_result():
    """Devuelve el JSON de debug si existe."""
    if not os.path.exists(DEBUG_JSON_PATH):
        return jsonify({"error": "no debug result saved yet"}), 404
    with open(DEBUG_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

# Ejemplo de integración en tu endpoint /ocr:
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    """
    Ejemplo simplificado: conservar tu lógica actual.
    Aquí llamamos a tu función de OCR que devuelve 'piezas' y dims,
    luego generamos el PDF (o lo genera tu pipeline) y lo devolvemos como application/pdf.
    """
    # 1) obtenemos la imagen y metadatos
    file = request.files.get("file")
    material = request.form.get("material")
    espesor = request.form.get("espesor")
    cliente = request.form.get("cliente")

    if not file:
        return jsonify({"error": "file missing"}), 400

    # Guarda temporalmente la imagen (opcional)
    tmp_img_path = "/tmp/last_uploaded.jpg"
    file.save(tmp_img_path)

    # 2) LLAMA AQUÍ A TU FUNCIÓN DE OCR existente
    # Debe devolver lista 'piezas' y 'image_width','image_height' en px y texto por pieza.
    # Por ejemplo:
    # piezas = [
    #   {"id":1,"nombre":"Lateral izquierdo","x":120,"y":200,"w":800,"h":400,"texto":"800 x 400 | 16mm | Cant:1"},
    #   ...
    # ]
    # image_w, image_h = 3000, 2000
    #
    # --- >>> reemplaza la siguiente línea por tu llamada real al OCR <<< ---
    piezas, image_w, image_h = run_your_ocr_and_get_pieces(tmp_img_path)  # implementa esta función
    # ---------------------------------------------------------------------

    # 3) guarda JSON de debug (para que lo puedas recuperar con /last_result.json)
    save_debug_json(piezas, image_w, image_h, meta={"material": material, "espesor": espesor, "cliente": cliente})

    # 4) genera el PDF (o usa tu lógica actual) y envíalo como response
    # Supongamos que tu pipeline genera '/tmp/output.pdf'
    output_pdf = "/tmp/output.pdf"
    generate_pdf_from_pieces(piezas, tmp_img_path, output_pdf)  # usa tu función real o la del punto 3
    # Devuelve el PDF binario
    return send_file(output_pdf, mimetype="application/pdf")
# ---------------------------------------------------------------------
