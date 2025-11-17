import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # ⬅️ para permitir CORS

# =========================
#  PDF DEMO EN BASE64
#  (así siempre devolvemos un PDF válido mientras montamos el OCR real)
# =========================
DEMO_PDF_BASE64 = (
    "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgaHR0cDovL3d3dy5y"
    "ZXBvcnRsYWIuY29tCjEgMCBvYmoKPDwKL0YxIDIgMCBSCi9GMiAzIDAgUgo+PgplbmRvYmoKMiAwIG9i"
    "ago8PAovVHlwZSAvRm9udAovU3VidHlwZSAvVHlwZTEKL05hbWUgL0YxCi9CYXNlRm9udCAvSGVsdmV0"
    "aWNhCi9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nCj4+CmVuZG9iagozIDAgb2JqCjw8Ci9UeXBlIC9G"
    "b250Ci9TdWJ0eXBlIC9UeXBlMQovTmFtZSAvRjIKL0Jhc2VGb250IC9IZWx2ZXRpY2EtQm9sZAovRW5j"
    "b2RpbmcgL1dpbkFuc2lFbmNvZGluZwo+PgplbmRvYmoKNCAwIG9iago8PAovVHlwZSAvUGFnZXMKL0tp"
    "ZHMgWzUgMCBSXQovQ291bnQgMQovTWVkaWFCb3ggWzAgMCA1OTUuMjc2IDg0MS44ODldCj4+CmVuZG9i"
    "ago1IDAgb2JqCjw8Ci9UeXBlIC9QYWdlCi9QYXJlbnQgNCAwIFIKL1Jlc291cmNlcyA8PAovRm9udCA8"
    "PAovRjEgMiAwIFIKL0YyIDMgMCBSCj4+PgovUHJvY1NldCAvUERGCj4+Ci9NZWRpYUJveCBbMCAwIDU5"
    "NS4yNzYgODQxLjg4OV0KL0NvbnRlbnRzIDYgMCBSCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9MZW5ndGgg"
    "MTk5Cj4+CnN0cmVhbQpCBiAwIDAgMCAwIDAKVGQKQkcgL0YxIDE0IFRmCjcyIDgwMiBUZChDYXJwaW50"
    "ZXItSUEgLSBQREYgZGVtbykgVGoKQlIKQkcgL0YyIDEyIFRmCjcyIDc4MiBUZChFc3RlIGVzIHVuIFBE"
    "RiBkZSBwcnVlYmEgZ2VuZXJhZG8gcG9yIENhcnBpbnRlci1JQS4pIFRqCkJSClQKQlIKZW5kc3RyZWFt"
    "CmVuZG9iagcKeHJlZgowIDcKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE3IDAwMDAwIG4gCjAw"
    "MDAwMDAxMDkgMDAwMDAgbiAKMDAwMDAwMDE5NCAwMDAwMCBuIAowMDAwMDAwMzE1IDAwMDAwIG4gCjAw"
    "MDAwMDA0NDggMDAwMDAgbiAKMDAwMDAwMDYyMyAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDcKL1Jv"
    "b3QgMSAwIFIKL0luZm8gNyAwIFIKPj4Kc3RhcnR4cmVmCjcxOQolJUVPRgo="
)

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

    # Por ahora devolvemos el PDF DEMO
    pdf_base64 = DEMO_PDF_BASE64
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

    # Aquí iría la generación real del PDF y Excel.
    # De momento devolvemos SIEMPRE el PDF DEMO.
    pdf_base64 = DEMO_PDF_BASE64
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
