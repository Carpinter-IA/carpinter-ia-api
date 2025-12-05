import os
import cv2
import numpy as np
import pytesseract
from pytesseract import Output
import math

# ==================== CONFIGURACIÓN TESSERACT (PORTABLE) ====================
import platform

TESSERACT_CMD_ENV = os.environ.get("TESSERACT_CMD")
TESSDATA_PREFIX_ENV = os.environ.get("TESSDATA_PREFIX")

if TESSERACT_CMD_ENV:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        default_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        pytesseract.pytesseract.tesseract_cmd = default_win
    else:
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

if TESSDATA_PREFIX_ENV:
    TESSDATA_DIR = TESSDATA_PREFIX_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"
    else:
        TESSDATA_DIR = "/usr/share/tessdata"

os.environ.pop("TESSDATA_PREFIX", None)
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

# ============================================================================

DEBUG_OVERLAY_PATH = "/tmp/debug_overlay.png"
LAST_JSON_PATH = "/tmp/last_result.json"


# ==================== FUNCIONES AUXILIARES ====================

def deskew_image(img):
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)

        thresh = cv2.threshold(gray, 0, 255,
                               cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        coords = np.column_stack(np.where(thresh > 0))
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except:
        return img


def detect_boxes(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    th = cv2.adaptiveThreshold(gray, 255,
                               cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV,
                               25, 15)

    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)

        if 40 < bw < w * 0.7 and 25 < bh < h * 0.25:
            boxes.append((x, y, bw, bh))

    return sorted(boxes, key=lambda b: (b[1], b[0]))


def ocr_box(img, box, lang="eng+spa"):
    x, y, w, h = box
    crop = img[y:y+h, x:x+w]

    config = "--psm 6 -c tessedit_char_whitelist=0123456789xX= "
    text = pytesseract.image_to_string(crop, lang=lang, config=config)
    return text.strip()


def parse_piece(text):
    text = text.replace(" ", "").lower()

    if "=" not in text or "x" not in text:
        return None

    try:
        cant, rest = text.split("=")
        largo, alto = rest.split("x")
        cant = int(cant)
        largo = int(largo)
        alto = int(alto)
        return {"cantidad": cant, "largo": largo, "ancho": alto}
    except:
        return None


# ==================== OCR PRINCIPAL ====================

def analyze_image(image_path, lang="eng+spa"):
    img = cv2.imread(image_path)
    if img is None:
        return []

    original_h, original_w = img.shape[:2]

    img = deskew_image(img)

    boxes = detect_boxes(img)

    overlay = img.copy()
    for (x, y, w, h) in boxes:
        cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 0, 255), 2)
    cv2.imwrite(DEBUG_OVERLAY_PATH, overlay)

    piezas = []

    # 1) Intento por cajas
    for box in boxes:
        text = ocr_box(img, box)
        p = parse_piece(text)
        if p:
            piezas.append(p)

    # 2) OCR global si fallo lo anterior
    if not piezas:
        config = "--psm 6 -c tessedit_char_whitelist=0123456789xX= "
        text = pytesseract.image_to_string(img, lang=lang, config=config)
        lines = text.split("\n")

        for ln in lines:
            p = parse_piece(ln)
            if p:
                piezas.append(p)

    # Guardamos json para /last_result.json
    import json
    with open(LAST_JSON_PATH, "w", encoding="utf8") as f:
        json.dump({
            "image_width": original_w,
            "image_height": original_h,
            "piezas": piezas,
            "meta": {"image_path": image_path}
        }, f, ensure_ascii=False)

    return piezas


# ==================== WRAPPER COMPATIBLE PARA app.py ====================

def run_ocr_and_get_pieces(image_path, debug_overlay=None, lang="eng+spa"):
    """
    Render espera EXACTAMENTE esta función.
    Retorna: (piezas, width, height)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)

    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"No se pudo leer la imagen {image_path}")

    h, w = img.shape[:2]

    piezas = analyze_image(image_path, lang=lang)

    if debug_overlay:
        if os.path.exists(DEBUG_OVERLAY_PATH):
            import shutil
            shutil.copy(DEBUG_OVERLAY_PATH, debug_overlay)

    return piezas, w, h
