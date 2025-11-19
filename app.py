import io
import base64
from typing import List, Dict

import requests
from flask import Flask, request, jsonify

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# =====================================================
#  1) ENDPOINT /health
# =====================================================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# =====================================================
#  2) FUNCIÓN OCR "DE PRUEBA"
#     (Luego aquí enchufaremos tu ocr_rayas_tesseract.py)
# =====================================================
def ocr_mock_desde_imagen_bytes(
    image_bytes: bytes,
    material: str = None,
    espesor: str = None,
    cliente: str = None,
) -> List[Dict]:
    """
    Esta función simula el resultado del OCR.
    Devuelve una lista de piezas con medidas.
    Más adelante la sustituiremos por tu OCR real.
    """

    piezas = [
        {
            "id": 1,
            "descripcion": "Lateral",
            "largo": 700,
            "ancho": 330,
            "espesor": espesor or "16 mm",
            "material": material or "Roble demo",
        },
        {
            "id": 2,
            "descripcion": "Tapa",
            "largo": 800,
            "ancho": 580,
            "espesor": espesor or "16 mm",
            "material": material or "Roble demo",
        },
        {
            "id": 3,
            "descripcion": "Base",
            "largo": 800,
            "ancho": 330,
            "espesor": espesor or "16 mm",
            "material": material or "Roble demo",
        },
    ]
    return piezas


# =====================================================
#  3) FUNCIÓN PARA GENERAR PDF MAESTRO
# =====================================================
def generar_pdf_maestro(
    cliente: str,
    material: str,
    espesor: str,
    piezas: List[Dict],
) -> bytes:
    """
    Genera un PDF sencillo con cabecera + lista de piezas.
    De momento no usa una plantilla gráfica, pero ya es
    el PDF “maestro” con medidas.
    """

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 40

    # Cabecera
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Carpinter-IA - Despiece")
    y -= 25

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Cliente / proyecto: {cliente or '-'}")
    y -= 14
    c.drawString(40, y, f"Material: {material or '-'}")
    y -= 14
    c.drawString(40, y, f"Espesor: {espesor or '-'}")
    y -= 22

    # Línea separadora
    c.line(40, y, width - 40, y)
    y -= 18

    # Cabecera tabla
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "ID")
    c.drawString(70, y, "Descripción")
    c.drawString(220, y, "Largo (mm)")
    c.drawString(300, y, "Ancho (mm)")
    c.drawString(390, y, "Espesor")
    c.drawString(460, y, "Material")
    y -= 14

    c.setFont("Helvetica", 10)

    for pieza in piezas:
        if y < 60:
            # Nueva página si no cabe
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "ID")
            c.drawString(70, y, "Descripción")
            c.drawString(220, y, "Largo (mm)")
            c.drawString(300, y, "Ancho (mm)")
            c.drawString(390, y, "Espesor")
            c.drawString(460, y, "Material")
            y -= 14
            c.setFont("Helvetica", 10)

        c.drawString(40, y, str(pieza.get("id", "")))
        c.drawString(70, y, str(pieza.get("descripcion", "")))
        c.drawString(220, y, str(pieza.get("largo", "")))
        c.drawString(300, y, str(pieza.get("ancho", "")))
        c.drawString(390, y, str(pieza.get("espesor", "")))
        c.drawString(460, y, str(pieza.get("material", "")))
        y -= 14

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# =====================================================
#  4) ENDPOINT /ocr  (usa la WebApp)
# =====================================================
@app.route("/ocr", methods=["POST"])
def ocr():
    """
    Recibe:
      - file (imagen)
      - material (opcional)
      - espesor  (opcional)
      - cliente  (opcional)

    Devuelve JSON:
      {
        "piezas": [...],
        "pdf_base64": "...",
        "xlsx_base64": ""
      }
    """

    if "file" not in request.files:
        return jsonify({"error": "Falta el archivo 'file' en multipart/form-data"}), 400

    file = request.files["file"]
    material = request.form.get("material")
    espesor = request.form.get("espesor")
    cliente = request.form.get("cliente")

    image_bytes = file.read()

    try:
        # 1) OCR (de momento mock)
        piezas = ocr_mock_desde_imagen_bytes(
            image_bytes=image_bytes,
            material=material,
            espesor=espesor,
            cliente=cliente,
        )

        # 2) Generar PDF maestro con esas piezas
        pdf_bytes = generar_pdf_maestro(
            cliente=cliente or "",
            material=material or "",
            espesor=espesor or "",
            piezas=piezas,
        )

        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return jsonify(
            {
                "piezas": piezas,
                "pdf_base64": pdf_b64,
                "xlsx_base64": "",  # más adelante generaremos también el Excel
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================
#  5) ENDPOINT /ocr_json (para GPT, usa image_url)
# =====================================================
@app.route("/ocr_json", methods=["POST"])
def ocr_json():
    """
    Espera un JSON:
    {
      "image_url": "https://....",
      "material": "Roble Aurora",
      "espesor": "16 mm",
      "cliente": "Carpintería X - Proyecto Y"
    }
    """

    data = request.get_json(silent=True) or {}
    image_url = data.get("image_url")

    if not image_url:
        return jsonify({"error": "Falta 'image_url' en el cuerpo JSON"}), 400

    material = data.get("material")
    espesor = data.get("espesor")
    cliente = data.get("cliente")

    try:
        # Descargar imagen
        resp = requests.get(image_url)
        if resp.status_code >= 400:
            raise ValueError(f"No se pudo descargar la imagen (status {resp.status_code})")

        image_bytes = resp.content

        # OCR mock
        piezas = ocr_mock_desde_imagen_bytes(
            image_bytes=image_bytes,
            material=material,
            espesor=espesor,
            cliente=cliente,
        )

        # Generar PDF maestro
        pdf_bytes = generar_pdf_maestro(
            cliente=cliente or "",
            material=material or "",
            espesor=espesor or "",
            piezas=piezas,
        )
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return jsonify(
            {
                "piezas": piezas,
                "pdf_base64": pdf_b64,
                "xlsx_base64": "",
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
