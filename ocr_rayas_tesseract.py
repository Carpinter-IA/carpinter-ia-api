# -*- coding: utf-8 -*-
"""
ocr_rayas_tesseract.py
OCR robusto para Carpinter-IA:
- preprocesado (CLAHE, denoise, adaptive threshold)
- deskew (rotación automática)
- detección de regiones de texto por morfología + contornos (versión permisiva)
- OCR por caja con varios PSM y combinación de resultados
- postprocesado regex para extraer (cantidad, largo x ancho)
- devuelve piezas con coords x,y,w,h para que app.py pueda dibujar overlays / rellenar PDF
"""

import os
import re
import sys
import csv
import platform
import numpy as np
import cv2
import pytesseract
from PIL import Image

# ==================== CONFIGURACIÓN TESSERACT (PORTABLE) ====================
# Detecta Windows vs Linux y permite override mediante variables de entorno
TESSERACT_CMD_ENV = os.environ.get("TESSERACT_CMD")
TESSDATA_PREFIX_ENV = os.environ.get("TESSDATA_PREFIX")

if TESSERACT_CMD_ENV:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        default_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_win):
            pytesseract.pytesseract.tesseract_cmd = default_win
        else:
            # dejamos la ruta por defecto como hint en Windows (si no existe dará error al ejecutar)
            pytesseract.pytesseract.tesseract_cmd = default_win
    else:
        # En contenedores Linux usualmente está en /usr/bin/tesseract
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

if TESSDATA_PREFIX_ENV:
    TESSDATA_DIR = TESSDATA_PREFIX_ENV
else:
    if os.name == "nt" or platform.system().lower().startswith("win"):
        TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"
    else:
        TESSDATA_DIR = "/usr/share/tessdata"

# Aseguramos que la variable de entorno esté puesta
os.environ.pop("TESSDATA_PREFIX", None)
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
# ============================================================================

# Parámetros ajustables
MAX_SIDE = 1600
OCR_TIMEOUT_LINE = 10
OCR_TIMEOUT_GLOBAL = 30
OCR_DEBUG = bool(os.environ.get("OCR_DEBUG", "") == "1")

def _log(*args, **kwargs):
    if OCR_DEBUG:
        print("[OCR DEBUG]", *args, **kwargs)

# Regex robusta para extraer pares: acepta "3 = 400 x 500", "3: 400x500", "400x500", etc.
_pair_pattern = re.compile(
    r"(?:\b(\d{1,2})\b\s*[:=\-]?\s*)?"  # cantidad opcional
    r"(\d{2,4})\s*[x×X]\s*(\d{2,4})"    # largo x ancho
)

def _extract_pairs_from_text(texto):
    texto = texto.replace("×", "x")
    texto = texto.replace(",", " ")
    out = []
    for m in _pair_pattern.finditer(texto):
        try:
            cant = int(m.group(1)) if m.group(1) else 1
            largo = int(m.group(2))
            ancho = int(m.group(3))
            if 30 <= largo <= 4000 and 30 <= ancho <= 4000 and 1 <= cant <= 99:
                out.append((cant, largo, ancho))
        except Exception:
            continue
    return out

# ==== Preprocesado y utilidades ====
def _resize_keep_aspect(img, max_side=MAX_SIDE):
    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return img, 1.0
    scale = max_side / float(max(h, w))
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale

def _deskew_image(gray):
    # intenta estimar la inclinación mediante minAreaRect de los pixeles oscuros
    coords = np.column_stack(np.where(gray < 128))
    if coords.shape[0] < 10:
        return gray, 0.0
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 1.0:
        return gray, 0.0
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle

def _preprocess(img_bgr):
    img = img_bgr.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # CLAHE
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass

    # denoise ligero
    gray = cv2.bilateralFilter(gray, 7, 75, 75)

    # deskew
    deskewed, angle = _deskew_image(gray)
    gray = deskewed

    # umbral adaptativo y máscara invertida
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 15, 8)
    inv = 255 - th

    # morfología para unir trazos (kernel rectangular horizontal)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15,3))
    morph = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel, iterations=1)

    return gray, morph, angle

# ==== Versión PERMISIVA de detección de cajas (reemplaza función antigua) ====
def _find_text_boxes(morph_mask):
    contours, _ = cv2.findContours(morph_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        area = w * h
        # Filtrado más permisivo para manuscritos pequeños
        if area < 500:
            continue
        if w < 40 or h < 12:
            continue
        # evitar cajas extremadamente estrechas y pequeñas
        if w/h < 0.6 and h < 20:
            continue
        boxes.append((x,y,w,h,area))
    # ordenar por y (de arriba a abajo)
    boxes = sorted(boxes, key=lambda b: b[1])
    # fusionar cajas cercanas (misma línea) — parámetros más permisivos
    merged = []
    for b in boxes:
        if not merged:
            merged.append(b)
        else:
            x,y,w,h,area = b
            px,py,pw,ph,parea = merged[-1]
            # si verticalmente muy cerca o solapan horizontalmente, unir
            if (y - (py+ph)) < 30 and (x < px+pw+40 and px < x+ w + 40):
                nx = min(x,px)
                ny = min(y,py)
                nw = max(x+w, px+pw) - nx
                nh = max(y+h, py+ph) - ny
                merged[-1] = (nx, ny, nw, nh, nw*nh)
            else:
                merged.append(b)
    return merged

# ==== OCR por caja combinando configuraciones ====
def _ocr_box_text(img_bgr, box, lang="eng+spa"):
    x,y,w,h,area = box
    pad = 6
    H, W = img_bgr.shape[:2]
    x0 = max(0, x-pad); y0 = max(0, y-pad)
    x1 = min(W, x+w+pad); y1 = min(H, y+h+pad)
    roi = img_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return ""
    pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))

    base_cfg = "-c tessedit_char_whitelist=0123456789xX:= -c classify_bln_numeric_mode=1 -c user_defined_dpi=200"
    results = []
    for psm in (7, 6, 11):
        cfg = f"{base_cfg} --psm {psm}"
        try:
            txt = pytesseract.image_to_string(pil, lang=lang, config=cfg, timeout=OCR_TIMEOUT_LINE)
        except RuntimeError:
            txt = ""
        txt = re.sub(r"[^\d xX:=]", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            results.append((psm, txt))
    if not results:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        pil2 = Image.fromarray(bw)
        try:
            txt2 = pytesseract.image_to_string(pil2, lang=lang, config=f"{base_cfg} --psm 6", timeout=OCR_TIMEOUT_LINE)
            txt2 = re.sub(r"[^\d xX:=]", " ", txt2)
            txt2 = re.sub(r"\s+", " ", txt2).strip()
            if txt2:
                results.append((6, txt2))
        except RuntimeError:
            pass

    best = ""
    best_score = -1
    for psm, t in results:
        digits = len(re.findall(r"\d", t))
        has_x = 2 if re.search(r"[xX]", t) else 0
        score = digits + has_x
        if score > best_score:
            best = t
            best_score = score
    return best

# ==== Función principal ====
def analyze_image(path, lang="eng+spa"):
    """
    Entrada: path a imagen
    Salida: lista de piezas con keys:
      cantidad, largo, ancho, cantos, ocr_texto, x, y, w, h
    """
    _log("Analyze image:", path)
    if not os.path.exists(path):
        _log("Imagen no encontrada:", path)
        return []

    img = cv2.imread(path)
    if img is None:
        _log("cv2.imread devolvió None")
        return []

    img, scale = _resize_keep_aspect(img, MAX_SIDE)
    ih, iw = img.shape[:2]
    _log("imagen resized:", iw, ih, "scale", scale)

    gray, morph, angle = _preprocess(img)
    _log("deskew angle:", angle)

    boxes = _find_text_boxes(morph)
    _log("boxes detectadas (post merge):", boxes)

    piezas = []
    seen_keys = set()
    for b in boxes:
        txt = _ocr_box_text(img, b, lang=lang)
        _log("OCR caja:", b, "=>", txt)
        if not txt or len(re.sub(r"\D", "", txt)) < 2:
            continue
        pares = _extract_pairs_from_text(txt)
        if not pares:
            # intentar lectura en una franja vertical ampliada alrededor de la caja
            x,y,w,h,area = b
            pad_h = int(h * 0.8)
            y0 = max(0, y - pad_h)
            y1 = min(ih, y + h + pad_h)
            strip = img[y0:y1, :]
            try:
                pil_strip = Image.fromarray(cv2.cvtColor(strip, cv2.COLOR_BGR2RGB))
                txt_strip = pytesseract.image_to_string(pil_strip, lang=lang, config="--psm 6", timeout=OCR_TIMEOUT_GLOBAL)
                txt_strip = re.sub(r"[^\d xX:=]", " ", txt_strip)
                txt_strip = re.sub(r"\s+", " ", txt_strip).strip()
                _log("OCR franja:", txt_strip)
                pares = _extract_pairs_from_text(txt_strip)
            except RuntimeError:
                pares = []
        if pares:
            for (cant, largo, ancho) in pares:
                piece = {
                    "cantidad": cant,
                    "largo": largo,
                    "ancho": ancho,
                    "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                    "ocr_texto": txt,
                    "x": int(b[0] / scale),
                    "y": int(b[1] / scale),
                    "w": int(b[2] / scale),
                    "h": int(b[3] / scale),
                }
                key = f"{cant}-{largo}-{ancho}-{piece['x']}-{piece['y']}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                piezas.append(piece)

    # fallback global si no hay nada
    if not piezas:
        _log("No se detectaron piezas por cajas; probando OCR global")
        try:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            txt_full = pytesseract.image_to_string(pil, lang=lang, config="--psm 6", timeout=OCR_TIMEOUT_GLOBAL)
            txt_full = re.sub(r"[^\d xX:=]", " ", txt_full)
            txt_full = re.sub(r"\s+", " ", txt_full).strip()
            _log("OCR global:", txt_full)
            for (cant, largo, ancho) in _extract_pairs_from_text(txt_full):
                piezas.append({
                    "cantidad": cant, "largo": largo, "ancho": ancho,
                    "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                    "ocr_texto": f"{cant} {largo}x{ancho}",
                    "x": 0, "y": 0, "w": iw, "h": ih
                })
        except RuntimeError:
            pass

    # dump CSV si se activa por env var
    if os.environ.get("OCR_DUMP_CSV") == "1":
        try:
            with open("resultado_despiece.csv", "w", newline="", encoding="utf-8") as f:
                wcsv = csv.writer(f)
                wcsv.writerow(["cantidad", "largo", "ancho", "x", "y", "w", "h", "texto"])
                for p in piezas:
                    wcsv.writerow([p["cantidad"], p["largo"], p["ancho"], p["x"], p["y"], p["w"], p["h"], p["ocr_texto"]])
        except Exception as e:
            _log("Error al escribir CSV:", e)

    _log("Piezas finales:", piezas)
    return piezas

# Si se ejecuta como script (pruebas locales)
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ocr_rayas_tesseract.py imagen.jpg")
        sys.exit(1)
    imgpath = sys.argv[1]
    res = analyze_image(imgpath, lang="eng+spa")
    print("RESULT:", res)
