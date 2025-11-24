# ============================================================
# app.py (VERSIÓN COMPLETA)
# Integrado con tu OCR real ocr_rayas_tesseract.py
# Compatible con Render (PORT dinámico)
# Genera JSON, overlay y PDF debug
# ============================================================

import os
import json
import tempfile
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# === Rutas temporales ===
DEBUG_JSON_PATH = "/tmp/carpinteria_last_result.json"
DEBUG_OVERLAY_PATH = "/tmp/debug_overlay.png"
OUTPUT_PDF_PATH = "/tmp/output_from_json.pdf"


# ============================================================
# 1) INTENTAR IMPORTAR TU OCR REAL
# ============================================================
try:
    from ocr_rayas_tesseract import analyze_image as _ocr_analyze
    app.logger.info("OCR externo cargado correctamente.")
except Exception as e:
    _ocr_analyze = None
    app.logger.warning(f"⚠️ No se pudo importar tu OCR real: {e}")


# ============================================================
# 2) WRAPPER PARA TU OCR REAL
# ============================================================
def run_ocr_and_get_pieces(image_path):
    """
    Llama a tu analyze_image del script ocr_rayas_tesseract.py.
    Debe devolver: (piezas, w, h)
    """

    # Si tu OCR no se pudo importar, devolvemos vacío pero sin romper nada.
    if _ocr_analyze is None:
        from PIL import Image as _Image
        im = _Image.open(image_path)
        w, h = im.size
        return [], w, h

    try:
        piezas = _ocr_analyze(image_path, lang="eng+spa")
    except TypeError:
        piezas = _ocr_analyze(image_path)

    # Si tu script ya devuelve (piezas, w, h) tal cual
    if isinstance(piezas, tuple) and len(piezas) == 3:
        return piezas

    # Si solo devuelve lista de piezas
    from PIL import Image as _Image
    im = _Image.open(image_path)
    w, h = im.size
    return piezas, w, h


# ============================================================
# 3) GUARDAR JSON DEBUG
# ============================================================
def save_debug_json(piezas, img_w, img_h, image_path=None, meta=None):
    data = {
        "piezas": piezas,
        "image_width": img_w,
        "image_height": img_h,
        "meta": meta or {}
    }
    if image_path:
        data["meta"]["image_path"] = image_path

    with open(DEBUG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 4) GENERAR OVERLAY CON CAJAS
# ============================================================
def generate_debug_overlay(json_path=DEBUG_JSON_PATH, out_path=DEBUG_OVERLAY_PATH):

    if not os.path.exists(json_path):
        raise FileNotFoundError("No debug JSON")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_path = data.get("meta", {}).get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise FileNotFoundError("No existe la imagen para overlay")

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    for p in data["piezas"]:
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        texto = p.get("texto") or p.get("ocr_texto") or "pieza"

        draw.rectangle([x, y, x+w, y+h], outline="red", width=3)
        draw.text((x+4, y+4), texto, fill="yellow", font=font)

    img.save(out_path)
    return out_path


# ============================================================
# 5) GENERAR PDF DE DEBUG (rectángulos)
# ============================================================
def pdf_from_json(json_path, image_path, out_pdf_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    piezas = data["piezas"]
    img_w = data["image_width"]
    img_h = data["image_height"]

    pdf_w, pdf_h = A4
    sx = pdf_w / img_w
    sy = pdf_h / img_h

    c = canvas.Canvas(out_pdf_path, pagesize=A4)
    c.setFont("Helvetica", 8)

    for p in piezas:
        x = p["x"] * sx
        y = pdf_h - (p["y"] + p["h"]) * sy

        c.setStrokeColorRGB(1, 0, 0)
        c.rect(x, y, p["w"]*sx, p["h"]*sy, stroke=1)

        txt = p.get("texto") or p.get("ocr_texto") or "pieza"
        c.drawString(x+3, y+3, txt)

    c.showPage()
    c.save()
    return out_pdf_path


# ============================================================
# 6) ENDPOINT PRINCIPAL
# ============================================================
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():

    file = request.files.get("file")

    if not file:
        return jsonify({"error": "Debe enviar un archivo"}), 400

    tmp_img = "/tmp/uploaded.jpg"
    file.save(tmp_img)

    piezas, w, h = run_ocr_and_get_pieces(tmp_img)

    save_debug_json(piezas, w, h, image_path=tmp_img)

    try:
        generate_debug_overlay()
    except Exception as e:
        app.logger.warning(f"Overlay falló: {e}")

    pdf_from_json(DEBUG_JSON_PATH, tmp_img, OUTPUT_PDF_PATH)

    return send_file(OUTPUT_PDF_PATH, mimetype="application/pdf")


# ============================================================
# 7) ENDPOINT JSON
# ============================================================
@app.route("/last_result.json")
def last_json():
    if not os.path.exists(DEBUG_JSON_PATH):
        return jsonify({"error": "no-debug"}), 404
    with open(DEBUG_JSON_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


# ============================================================
# 8) ENDPOINT OVERLAY
# ============================================================
@app.route("/debug_overlay.png")
def overlay():
    if not os.path.exists(DEBUG_OVERLAY_PATH):
        return jsonify({"error": "overlay-not-found"}), 404
    return send_file(DEBUG_OVERLAY_PATH, mimetype="image/png")


# ============================================================
# 9) ARRANQUE RENDER
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
