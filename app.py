from flask import Flask, request, jsonify, send_file
import os, tempfile, uuid, traceback, shutil, subprocess, werkzeug

# Importar OCR
from ocr_rayas_tesseract import analyze_image, exportar_pdf_maestro

app = Flask(__name__)

# ======== CONFIGURACIÓN TESSSERACT ===========
# En Render (Linux)
os.environ.setdefault("TESSDATA_PREFIX", "/usr/share/tesseract-ocr/5/tessdata")

# Fuerza el binario correcto para pytesseract
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
except Exception as e:
    print("⚠️ No se pudo inicializar pytesseract:", e)

PDF_MAESTRO_PATH = os.environ.get("PDF_MAESTRO_PATH", "Carpinter-IA_Despiece.pdf")

# ============================================

@app.get("/")
def root():
    return "✅ Carpinter-IA API online. Prueba /health, /diag o POST /ocr"

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/diag")
def diag():
    # Comprobaciones básicas
    try:
        import pytesseract, cv2
        t_path = shutil.which("tesseract")
        t_ver = str(pytesseract.get_tesseract_version())
        langs = subprocess.check_output(
            ["tesseract", "--list-langs"], stderr=subprocess.STDOUT, text=True
        )
        return jsonify({
            "tesseract_path": t_path,
            "tesseract_version": t_ver,
            "tessdata_prefix": os.environ.get("TESSDATA_PREFIX"),
            "tesseract_langs": langs.splitlines(),
            "opencv_version": cv2.__version__,
        })
    except Exception as e:
        return jsonify({"diag_error": str(e), "trace": traceback.format_exc()}), 500

@app.post("/ocr")
def ocr_endpoint():
    try:
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

    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)



