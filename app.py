from flask import Flask, request, jsonify, send_file
import os, tempfile, uuid
import werkzeug

# Importa tus funciones locales
from ocr_rayas_tesseract import analyze_image, exportar_pdf_maestro

app = Flask(__name__)

# En Linux (Render), Tesseract suele vivir aquí
os.environ.setdefault("TESSDATA_PREFIX", "/usr/share/tesseract-ocr/5/tessdata")

# PDF maestro dentro del repo
PDF_MAESTRO_PATH = os.environ.get("PDF_MAESTRO_PATH", "Carpinter-IA_Despiece.pdf")

@app.get("/")
def root():
    return "✅ Carpinter-IA API online. Prueba /health o POST /ocr"

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/ocr")
def ocr_endpoint():
    """
    form-data:
      file = imagen (jpg/png/pdf)
      lang = 'eng+spa' por defecto
      return_pdf = 'true' si quieres el PDF maestro rellenado
    """
    if "file" not in request.files:
        return jsonify({"error": "Sube un archivo en el campo 'file'"}), 400

    f: werkzeug.datastructures.FileStorage = request.files["file"]
    lang = request.form.get("lang", "eng+spa")
    return_pdf = request.form.get("return_pdf", "false").lower() == "true"

    with tempfile.TemporaryDirectory() as tmpdir:
        fname = str(uuid.uuid4()) + "_" + werkzeug.utils.secure_filename(f.filename)
        img_path = os.path.join(tmpdir, fname)
        f.save(img_path)

        piezas = analyze_image(img_path, lang=lang)
        if not piezas:
            return jsonify({"piezas": [], "message": "No se detectaron piezas"}), 200

        if return_pdf:
            out_pdf = os.path.join(tmpdir, "resultado_despiece.pdf")
            exportar_pdf_maestro(piezas, maestro_path=PDF_MAESTRO_PATH, salida_path=out_pdf)
            return send_file(out_pdf, as_attachment=True, download_name="resultado_despiece.pdf")

        return jsonify({"piezas": piezas, "lang": lang})

if __name__ == "__main__":
    # Render asigna el puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
