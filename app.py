import os
import uuid
import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Carpeta donde guardamos las imágenes subidas
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
#  ENDPOINT /health
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# =========================
#  FUNCIÓN DE OCR (AQUÍ ENGANCHAS TU SCRIPT REAL)
# =========================
def procesar_imagen_ocr(image_bytes, diseno=None, material=None, espesor=None):
    """
    AQUÍ debes llamar a tu script real ocr_rayas_tesseract.py.
    De momento devolvemos datos de prueba para comprobar el flujo.
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

    # De momento sin PDF/Excel reales (solo para probar)
    pdf_base64 = ""
    xlsx_base64 = ""

    return piezas, pdf_base64, xlsx_base64


# =========================
#  1) SUBIR IMAGEN Y OBTENER ID  (/upload)
# =========================
@app.route("/upload", methods=["GET", "POST"])
def upload_despiece():
    if request.method == "GET":
        # Formulario sencillo para subir la foto del despiece
        return """
        <html>
          <body>
            <h2>Subir despiece Carpinter-IA</h2>
            <form method="post" enctype="multipart/form-data">
              <input type="file" name="file" accept="image/*" required>
              <button type="submit">Subir</button>
            </form>
          </body>
        </html>
        """

    # POST: guardamos el archivo y devolvemos un ID
    file = request.files.get("file")
    if not file:
        return "Falta el archivo (campo 'file')", 400

    despiece_id = uuid.uuid4().hex[:8]  # por ejemplo "a3f9c21b"
    _, ext = os.path.splitext(file.filename)
    if not ext:
        ext = ".jpg"
    filename = f"{despiece_id}{ext.lower()}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    return f"""
    <html>
      <body>
        <h2>Despiece subido correctamente ✅</h2>
        <p>ID de despiece (cópialo y llévalo a tu Chat Carpinter-IA):</p>
        <pre style="font-size:20px;">{despiece_id}</pre>
      </body>
    </html>
    """


# =========================
#  2) PROCESAR POR ID  (/ocr_id)  → ESTE ES EL QUE USARÁ EL GPT
# =========================
@app.route("/ocr_id", methods=["POST"])
def ocr_id():
    """
    Recibe:
      - despiece_id: ID devuelto por /upload
      - diseno, material, espesor: datos de contexto
    """

    data = request.get_json(silent=True) or {}
    despiece_id = data.get("despiece_id")

    if not despiece_id:
        return jsonify({"error": "Falta 'despiece_id' en el cuerpo JSON"}), 400

    # Buscar el archivo correspondiente en la carpeta uploads
    # (buscamos cualquier extensión que empiece por ese ID)
    filename = None
    for f in os.listdir(UPLOAD_FOLDER):
        if f.startswith(despiece_id):
            filename = f
            break

    if not filename:
        return jsonify({"error": "No existe ninguna imagen para ese despiece_id"}), 404

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "rb") as f:
        image_bytes = f.read()

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
#  3)
