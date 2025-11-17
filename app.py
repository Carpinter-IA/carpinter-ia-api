import io
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # para permitir CORS
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# Permitir CORS desde cualquier origen (tu WebApp, etc.)
CORS(app, resources={r"/*": {"origins": "*"}})


# =========================
#  /health  → para ver si está vivo
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# =========================
#  Función auxiliar: generar un PDF DEMO
# =========================
def generar_pdf_demo(diseno=None, material=None, espesor=None, cliente=None):
    """
    Genera un PDF muy sencillo con la info básica y lo devuelve en base64 (str).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    titulo = "Carpinter-IA - PDF demo"
    subtitulo = "Versión de prueba WebApp (sin OCR real todavía)"

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, titulo)

    c.setFont("Helvetica", 12)
    c.drawString(72, height - 96, subtitulo)

    y = height - 140
    c.setFont("Helvetica", 11)

    if cliente:
        c.drawString(72, y, f"Cliente / proyecto: {cliente}")
        y -= 18
    if diseno:
        c.drawString(72, y, f"Diseño: {diseno}")
        y -= 18
    if material:
        c.drawString(72, y, f"Material: {material}")
        y -= 18
    if espesor:
        c.drawString(72, y, f"Espesor: {espesor}")
        y -= 18

    c.drawString(72, y - 10, "Este PDF es solo de prueba para validar el flujo WebApp → API → PDF.")
    c.drawString(72, y - 28, "Más adelante aquí irá el despiece real generado por Carpinter-IA.")

    c.showPage()
    c.save()

    buffer.seek(0)
    pdf_bytes = buffer.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    return pdf_b64


# =========================
#  Función de “OCR” de prueba con URL
#  (la usaremos desde /ocr_json)
# =========================
def procesar_imagen_ocr_desde_url(image_url, diseno=None, material=None, espesor=None):
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

    # PDF DEMO
    pdf_base64 = generar_pdf_demo(diseno=diseno, material=material, espesor=espesor)
    xlsx_base64 = ""  # de momento vacío

    return piezas, pdf_base64, xlsx_base64


# =========================
#  Función de “OCR” de prueba con archivo subido (file)
#  (la usaremos desde /ocr)
# =========================
def procesar_imagen_ocr_desde_file(file_storage, diseno=None, material=None, espesor=None, cliente=None):
    """
    file_storage: objeto FileStorage que viene de request.files['file']
    Aquí, más adelante, engancharás tu ocr_rayas_tesseract.py usando los bytes de la imagen.
    """
    # Leemos los bytes de la imagen (de momento no los usamos)
    _ = file_storage.read()

    # Piezas de prueba, igual que arriba (puedes cambiarlas cuando pongas tu OCR real)
    piezas = [
        {
            "id": 1,
            "descripcion": "Lateral",
            "largo": 700,
            "ancho": 330,
            "espesor": espesor,
            "material": material,
            "diseno": diseno or cliente,
        },
        {
            "id": 2,
            "descripcion": "Tapa",
            "largo": 800,
            "ancho": 580,
            "espesor": espesor,
            "material": material,
            "diseno": diseno or cliente,
        },
    ]

    # PDF DEMO con datos del formulario
    pdf_base64 = generar_pdf_demo(
        diseno=diseno,
        material=material,
        espesor=espesor,
        cliente=cliente,
    )
    xlsx_base64 = ""

    return piezas, pdf_base64, xlsx_base64


# =========================
#  /ocr_json  → endpoint que usa el GPT (con image_url)
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
        piezas, pdf_base64, xlsx_base64 = procesar_imagen_ocr_desde_url(
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


# =========================
#  /ocr  → endpoint para la WebApp (subida de archivo)
# =========================
@app.route("/ocr", methods=["POST"])
def ocr_file():
    """
    Espera un formulario multipart/form-data así:
      - file: fichero de imagen (campo obligatorio)
      - diseno: texto opcional
      - material: texto opcional
      - espesor: texto opcional
      - cliente: texto opcional (nombre del cliente/proyecto)
    """
    if "file" not in request.files:
        return jsonify({"error": "Falta el archivo 'file' en el formulario"}), 400

    file = request.files["file"]

    diseno = request.form.get("diseno")
    material = request.form.get("material")
    espesor = request.form.get("espesor")
    cliente = request.form.get("cliente")

    try:
        piezas, pdf_base64, xlsx_base64 = procesar_imagen_ocr_desde_file(
            file_storage=file,
            diseno=diseno,
            material=material,
            espesor=espesor,
            cliente=cliente,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "piezas": piezas,
            "pdf_base64": pdf_base64,
            "xlsx_base64": xlsx_base64,
            "diseno": diseno or cliente,
            "material": material,
            "espesor": espesor,
            "cliente": cliente,
        }
    ), 200


if __name__ == "__main__":
    # Solo para pruebas locales, en Render se usa gunicorn
    app.run(host="0.0.0.0", port=8000, debug=True)
