# app.py
# Requisitos: pip install flask pillow reportlab
# Uso: python app.py
# Nota: reemplaza la función run_ocr_and_get_pieces(...) por tu OCR real.

import os
import json
import tempfile
from flask import Flask, request, send_file, jsonify, abort
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# Rutas / nombres
DEBUG_JSON_PATH = "/tmp/carpinteria_last_result.json"
DEBUG_OVERLAY_PATH = "/tmp/debug_overlay.png"
OUTPUT_PDF_PATH = "/tmp/output_from_json.pdf"

# ------------------------------
# UTIL: guardar JSON de debug
# ------------------------------
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

# ------------------------------
# UTIL: generar overlay debug sobre la imagen (debug_overlay.png)
# ------------------------------
def generate_debug_overlay(json_path=None, out_path=DEBUG_OVERLAY_PATH):
    if not json_path:
        json_path = DEBUG_JSON_PATH
    if not os.path.exists(json_path):
        raise FileNotFoundError("Debug JSON not found: " + json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    image_path = meta.get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise FileNotFoundError("Image not found for overlay: " + str(image_path))

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    for p in data.get("piezas", []):
        x = int(p.get("x", 0))
        y = int(p.get("y", 0))
        w = int(p.get("w", 0))
        h = int(p.get("h", 0))
        text = str(p.get("texto", p.get("nombre", "")))
        draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0, 200), width=3)
        draw.text((x + 6, max(y - 18, y + 4)), text, fill=(255, 255, 0, 255), font=font)

    img.save(out_path)
    app.logger.info(f"Debug overlay saved to {out_path}")
    return out_path

# ------------------------------
# UTIL: convertir JSON -> PDF con conversión px -> pt (ReportLab)
# ------------------------------
def pdf_from_json(json_path, image_path, out_pdf_path, page_size=A4):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    piezas = data.get("piezas", [])
    img_w_px = data.get("image_width")
    img_h_px = data.get("image_height")

    # Si no vienen dimensiones en JSON, las extraemos de la imagen
    if not img_w_px or not img_h_px:
        im = Image.open(image_path)
        img_w_px, img_h_px = im.size

    pdf_w_pt, pdf_h_pt = page_size
    scale_x = pdf_w_pt / img_w_px
    scale_y = pdf_h_pt / img_h_px

    c = canvas.Canvas(out_pdf_path, pagesize=page_size)
    c.setFont("Helvetica", 9)

    for p in piezas:
        x_px = p.get("x", 0)
        y_px = p.get("y", 0)
        w_px = p.get("w", 0)
        h_px = p.get("h", 0)
        texto = str(p.get("texto", p.get("nombre", "")))

        # convertir coordenadas
        x_pt = x_px * scale_x
        # invertir eje Y: en PDF Y=0 está abajo
        y_pt = pdf_h_pt - (y_px + h_px) * scale_y

        # Opcional: dibujar rect para verificar alineación (puedes comentar)
        c.setStrokeColorRGB(1, 0, 0)
        c.setLineWidth(0.5)
        c.rect(x_pt, y_pt, w_px * scale_x, h_px * scale_y, stroke=1, fill=0)

        # Escribir texto dentro de la caja
        text_x = x_pt + 4
        text_y = y_pt + 4
        c.setFillColorRGB(0, 0, 0)
        c.drawString(text_x, text_y, texto)

    c.showPage()
    c.save()
    app.logger.info(f"PDF generated at {out_pdf_path}")
    return out_pdf_path

# ------------------------------
# PLACEHOLDER OCR (REEMPLAZA por tu OCR real)
# ------------------------------
def run_ocr_and_get_pieces(image_path):
    """
    Esta función es un placeholder. Debes reemplazarla por tu OCR real que:
      - tome la imagen en image_path
      - devuelva (piezas, image_width, image_height)
    Aquí devolvemos algunos datos de ejemplo para que puedas probar el flujo.
    """
    im = Image.open(image_path)
    img_w, img_h = im.size

    # Ejemplo: 3 piezas en posiciones aproximadas (ajusta o sustituye)
    piezas = [
        {"id": 1, "nombre": "Lateral izquierdo", "x": int(img_w*0.05), "y": int(img_h*0.10), "w": int(img_w*0.4), "h": int(img_h*0.12), "texto": "Lateral 800x400 | 16mm | Cant:1"},
        {"id": 2, "nombre": "Base", "x": int(img_w*0.05), "y": int(img_h*0.25), "w": int(img_w*0.4), "h": int(img_h*0.12), "texto": "Base 700x400 | 16mm | Cant:1"},
        {"id": 3, "nombre": "Estante", "x": int(img_w*0.05), "y": int(img_h*0.40), "w": int(img_w*0.4), "h": int(img_h*0.12), "texto": "Estante 600x300 | 16mm | Cant:2"},
    ]
    return piezas, img_w, img_h

# ------------------------------
# ENDPOINT: devuelve JSON debug
# ------------------------------
@app.route("/last_result.json", methods=["GET"])
def last_result():
    if not os.path.exists(DEBUG_JSON_PATH):
        return jsonify({"error": "no debug result saved yet"}), 404
    with open(DEBUG_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

# ------------------------------
# ENDPOINT: /ocr (recibe la imagen y devuelve PDF)
# ------------------------------
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    # recibe multipart/form-data
    file = request.files.get("file")
    material = request.form.get("material")
    espesor = request.form.get("espesor")
    cliente = request.form.get("cliente")

    if not file:
        return jsonify({"error": "file missing"}), 400

    # guarda la imagen subida en /tmp
    tmp_dir = tempfile.gettempdir()
    img_fname = "last_uploaded.jpg"
    tmp_img_path = os.path.join(tmp_dir, img_fname)
    file.save(tmp_img_path)
    app.logger.info(f"Saved uploaded image to {tmp_img_path}")

    # Llama a tu OCR real aquí:
    piezas, image_w, image_h = run_ocr_and_get_pieces(tmp_img_path)
    # Guarda JSON de debug con ruta de la imagen
    save_debug_json(piezas, image_w, image_h, image_path=tmp_img_path, meta={"material": material, "espesor": espesor, "cliente": cliente})

    # Genera un overlay debug (archivo PNG) para revisar visualmente
    try:
        generate_debug_overlay(DEBUG_JSON_PATH, out_path=DEBUG_OVERLAY_PATH)
    except Exception as e:
        app.logger.warning("Could not generate debug overlay: " + str(e))

    # Genera PDF a partir del JSON (con conversion px->pt)
    try:
        pdf_from_json(DEBUG_JSON_PATH, tmp_img_path, OUTPUT_PDF_PATH)
    except Exception as e:
        app.logger.error("PDF generation failed: " + str(e))
        return jsonify({"error": "pdf generation failed", "detail": str(e)}), 500

    # Devuelve el PDF binario
    return send_file(OUTPUT_PDF_PATH, mimetype="application/pdf")

# ------------------------------
# ENDPOINT: servir overlay debug (opcional)
# ------------------------------
@app.route("/debug_overlay.png", methods=["GET"])
def get_overlay():
    if not os.path.exists(DEBUG_OVERLAY_PATH):
        return jsonify({"error": "debug overlay not found"}), 404
    return send_file(DEBUG_OVERLAY_PATH, mimetype="image/png")

# ------------------------------
# Arranque del servidor
# ------------------------------
if __name__ == "__main__":
    # Puerto 5000 localmente; en Render usará su configuración de puerto
    app.run(host="0.0.0.0", port=5000, debug=True)
