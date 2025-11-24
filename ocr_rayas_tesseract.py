# ==================== CONFIGURACIÓN TESSERACT (PORTABLE) ====================
# Detecta Windows vs Linux y permite override mediante variables de entorno
import platform

# Prioridad: variables de entorno (útil en Render/Docker)
TESSERACT_CMD_ENV = os.environ.get("TESSERACT_CMD")
TESSDATA_PREFIX_ENV = os.environ.get("TESSDATA_PREFIX")

if TESSERACT_CMD_ENV:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        # Windows: usa la ruta estándar si existe, si no dejamos la variable para el usuario
        default_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_win):
            pytesseract.pytesseract.tesseract_cmd = default_win
        else:
            # No hay tesseract en la ruta Windows estándar; dejamos la variable apuntando al valor por defecto
            pytesseract.pytesseract.tesseract_cmd = default_win
    else:
        # Linux (Render): ruta típica de tesseract instalable por apt
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# TESSDATA_PREFIX similar: variable de entorno o ruta por defecto
if TESSDATA_PREFIX_ENV:
    TESSDATA_DIR = TESSDATA_PREFIX_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"
    else:
        TESSDATA_DIR = "/usr/share/tessdata"

# Aplicar la variable de entorno (asegura que pytesseract la vea)
os.environ.pop("TESSDATA_PREFIX", None)
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

# Fin configuración Tesseract portátil
# ============================================================================
