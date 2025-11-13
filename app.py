import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
#  ENDPOINT /health
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# =========================
#  FUNCIÓN DE OCR (A RELLENAR CON TU LÓGICA REAL)
# =========================
def procesar_imagen_ocr(image_bytes, diseno=None, material=None, espesor=None):
    """
    Aquí engancharás tu script real de OCR (ocr_rayas_tesseract.py).
    De momento devolvemos datos de prueba para asegurarnos de que todo el flujo funciona.
    """

    piezas = [
        {
            "id": 1,
            "descripcion": "Lateral",
            "largo": 700,
            "ancho": 330,
            "espesor": espesor,
            "material": material,
            "diseno": diseno,
        },
        {
            "id": 2,
            "descripcion": "Tapa",
            "largo": 800,
            "ancho": 580,
            "espesor": espesor,
            "material": material,
            "diseno": diseno,
        },
    ]

    # De momento sin PDF/Excel reales (solo para probar que llega la imagen)
    pdf_base64 = ""
    xlsx_base64 = ""

    return piezas, pdf_base64, xlsx_base64


# =========================
#  ENDPOINT /ocr_json (EL QUE USA ChatGPT)
# =========================
@app.route("/ocr_json", methods=["POST"])
def ocr_json():
    """
    Recibe:
      - image_url: URL pública de la imagen que ChatGPT ha subido
      - diseno, material, espesor: textos opcionales

    ChatGPT manda un JSON con esos campos.
    """

    data = request.get_json(silent=True) or {}

    image_url = data.get("image_url")
    if not image_url:
        return jsonify({"error": "Falta 'image_url' en el cuerpo JSON"}), 400

    try:
        # Descargar la imagen desde la URL
        resp = requests.get(image_url)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"No se pudo descargar la imagen desde image_url: {e}"}), 400

    image_bytes = resp.content

    diseno = data.get("diseno")
    material = data.get("material")
    espesor = data.get("espesor")

    piezas, pdf_base64, xlsx_base64 = procesar_imagen_ocr(
        image_bytes=image_bytes,
        diseno=diseno,
        material=material,
        espesor=espesor,
    )

    return jsonify({
        "piezas": piezas,
        "pdf_base64": pdf_base64,
        "xlsx_base64": xlsx_base64,
    }), 200


# =========================
#  ENDPOINT /ocr (lo dejamos por compatibilidad, pero el GPT YA NO lo usa)
# =========================
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "Sube un archivo en el campo 'file'"}), 400

    image_bytes = file.read()

    diseno = request.form.get("diseno")
    material = request.form.get("material")
    espesor = request.form.get("espesor")

    piezas, pdf_base64, xlsx_base64 = procesar_imagen_ocr(
        image_bytes=image_bytes,
        diseno=diseno,
        material=material,
        espesor=espesor,
    )

    return jsonify({
        "piezas": piezas,
        "pdf_base64": pdf_base64,
        "xlsx_base64": xlsx_base64,
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
