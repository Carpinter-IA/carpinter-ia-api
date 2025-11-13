import requests
from flask import Flask, request, jsonify

app = Flask(__name__)


# =========================
#  /health  → para ver si está vivo
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# =========================
#  Función de “OCR” de prueba
#  (aquí luego engancharás tu ocr_rayas_tesseract.py)
# =========================
def procesar_imagen_ocr(image_url, diseno=None, material=None, espesor=None):
    # 1. Probar que la imagen se puede descargar
    resp = requests.get(image_url)
    if resp.status_code >= 400:
        raise ValueError(f"No se pudo descargar la imagen (status {resp.status_code})")

    # 2. De momento devolvemos piezas de prueba
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

    pdf_base64 = ""   # de momento vacío
    xlsx_base64 = ""  # de momento vacío

    return piezas, pdf_base64, xlsx_base64


# =========================
#  /ocr_json  → el endpoint que usa el GPT
# =========================
@app.route("/ocr_json", methods=["POST"])
def ocr_json():
    """
    Espera un JSON así:
    {
      "image_url": "https://....",
      "diseno": "Mueble TV",
      "material": "Roble Aurora",
      "espesor": "16"
    }
    """
    data = request.get_json(silent=True) or {}

    image_url = data.get("image_url")
    if not image_url:
        return jsonify({"error": "Falta 'image_url' en el cuerpo JSON"}), 400

    diseno = data.get("diseno")
    material = data.get("material")
    espesor = data.get("espesor")

    try:
        piezas, pdf_base64, xlsx_base64 = procesar_imagen_ocr(
            image_url=image_url,
            diseno=diseno,
            material=material,
            espesor=espesor,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "piezas": piezas,
            "pdf_base64": pdf_base64,
            "xlsx_base64": xlsx_base64,
        }
    ), 200


if __name__ == "__main__":
    # Solo para pruebas locales, en Render se usa gunicorn
    app.run(host="0.0.0.0", port=8000, debug=True)
