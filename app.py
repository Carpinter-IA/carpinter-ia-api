# app.py
# Requisitos: Flask, Pillow, reportlab (ya los tienes en requirements.txt)
# Importante para Render: usa el puerto pasado por la variable PORT

import os
import json
import tempfile
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# === RUTAS INTERNAS ===
DEBUG_JSON_PATH = "/tmp/carpinteria_last_result.json"
DEBUG_OVERLAY_PATH = "/tmp/debug_overlay.png"
OUTPUT_PDF_PATH = "/tmp/output_from_json.pdf"

# --------------------------------------------------------------
# GUARDAR JSON DE DEBUG
# --------------------------------------------------------------
def save_debug_json(piezas, image_width, image_height, image_path=None, meta=None):
    payload = {
        "piezas": piezas,
        "image_width": image_width,
        "image_height": image_height,
        "meta": meta or {}
    }
    if image_path:
        payload["meta"]["image_path"] = image_path

    with open(DEBUG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    app.logger.info(f"Debug JSON saved to {DEBUG_JSON_PATH}")


# --------------------------------------------------------------
# CREAR OVERLAY (IMAGEN CON CAJAS)
# --------------------------------------------------------------
def generate_debug_overlay(json_path=DEBUG_JSON_PATH, out_path=DEBUG_OVERLAY_PATH):

    if not os.path.exists(json_path):
        raise FileNotFoundError("Debug JSON not found.")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_path = data.get("meta", {}).get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise FileNotFoundError("Image for overlay not found.")

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    for p in data.get("piezas", []):
        x = int(p["x"])
        y = int(p["y"])
        w = int(p["w"])
        h = int(p["h"])
        texto = p.get("texto", p.get("nombre", ""))

        draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
        draw.text((x + 4, y + 4), texto, fill="yellow", font=font)

    img.save(out_path)
    app.logger.info(f"Debug overlay saved at {out_path}")
    return out_path


# --------------------------------------------------------------
# GENERAR PDF A PARTIR DEL JSON (CONVERSIÓN px → pt)
# --------------------------------------------------------------
def pdf_from_json(json_path, image_path, out_pdf_path):

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    piezas = data["piezas"]
    img_w = data["image_width"]
    img_h = data["image_height"]

    pdf_w, pdf_h = A4
    scale_x = pdf_w / img_w
    scale_y = pdf_h / img_h

    c = canvas.Canvas(out_pdf_path, pagesize=A4)
    c.setFont("Helvetica", 9)

    for p in piezas:
        x = p["x"]
        y = p["y"]
        w = p["w"]
        h = p["h"]
        texto = p.get("texto", p.get("nombre", ""))

        # Conversión px → puntos PDF
        x_pt = x * scale_x
        y_pt = pdf_h - (y + h) * scale_y  # invertir eje Y

        # Rectángulo de debug
        c.setStrokeColorRGB(1, 0, 0)
        c.setLineWidth(0.5)
        c.rect(x_pt, y_pt, w * scale_x, h * scale_y, stroke=1)

        # Texto dentro
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x_pt + 4, y_pt + 4, texto)

    c.showPage()
    c.save()
    return out_pdf_path


# --------------------------------------------------------------
# OCR PLACEHOLDER (SUSTITUYE POR TU OCR REAL)
# --------------------------------------------------------------
def run_ocr_and_get_pieces(image_path):
    """Devuelve piezas simuladas. Sustituye por tu OCR real."""
    im = Image.open(image_path)
    w, h = im.size

    piezas_ejemplo = [
        {"id": 1, "nombre": "Lateral", "x": int(w*0.05), "y": int(h*0.10), "w": int(w*0.4), "h": int(h*0.1),
         "texto": "Lateral | 800x400 | 16mm | 1u"},
        {"id": 2, "nombre": "Base", "x": int(w*0.05), "y": int(h*0.30), "w": int(w*0.4), "h": int(h*0.1),
         "texto": "Base | 700x400 | 16mm | 1u"},
    ]

    return piezas_ejemplo, w, h


# --------------------------------------------------------------
# ENDPOINT: JSON DEBUG
# --------------------------------------------------------------
@app.route("/last_result.json")
def last_result():
    if not os.path.exists(DEBUG_JSON_PATH):
        return jsonify({"error": "no debug result"}), 404

    with open(DEBUG_JSON_PATH, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


# --------------------------------------------------------------
# ENDPOINT PRINCIPAL OCR → PDF
# --------------------------------------------------------------
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():

    file = request.files.get("file")
    material = request.form.get("material")
    espesor = request.form.get("espesor")
    cliente = request.form.get("cliente")

    if not file:
        return jsonify({"error": "file missing"}), 400

    # Guardar imagen subida
    tmp_img_path = "/tmp/uploaded.jpg"
    file.save(tmp_img_path)

    # Llamar a tu OCR real
    piezas, w, h = run_ocr_and_get_pieces(tmp_img_path)

    # Guardar JSON debug
    save_debug_json(
        piezas,
        w,
        h,
        image_path=tmp_img_path,
        meta={"material": material, "espesor": espesor, "cliente": cliente}
    )

    # Crear OVERLAY de debug
    try:
        generate_debug_overlay()
    except Exception as e:
        app.logger.warning(f"Overlay error: {e}")

    # Crear PDF final
    try:
        pdf_from_json(DEBUG_JSON_PATH, tmp_img_path, OUTPUT_PDF_PATH)
    except Exception as e:
        return jsonify({"error": "pdf generation failed", "detail": str(e)}), 500

    return send_file(OUTPUT_PDF_PATH, mimetype="application/pdf")


# --------------------------------------------------------------
# ENDPOINT: overlay
# --------------------------------------------------------------
@app.route("/debug_overlay.png")
def overlay():
    if not os.path.exists(DEBUG_OVERLAY_PATH):
        return jsonify({"error": "overlay not found"}), 404
    return send_file(DEBUG_OVERLAY_PATH, mimetype="image/png")


# --------------------------------------------------------------
# ARRANQUE (RENDER)
# --------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
