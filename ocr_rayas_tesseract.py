# -*- coding: utf-8 -*-
"""
ocr_rayas_tesseract.py
OCR robusto para Carpinter-IA:
- preprocesado (CLAHE, denoise, threshold)
- deskew (rotación automática)
- detección de cajas de texto por contornos
- OCR por caja con varios psm y combinación de resultados
- extracción de parejas (cantidad, largo x ancho)

Requisitos: opencv-python-headless, pytesseract, numpy, Pillow
"""

import os
import re
import sys
import time
import math
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
# Parámetros ajustables
MAX_SIDE = 1600
OCR_TIMEOUT_LINE = 10
OCR_TIMEOUT_GLOBAL = 30
OCR_DEBUG = bool(os.environ.get("OCR_DEBUG", "") == "1")

# ==== Helpers / utilidades ====
def _log(*args, **kwargs):
    if OCR_DEBUG:
        print("[OCR DEBUG]", *args, **kwargs)

# regex mejorada para pares: acepta "3 = 400 x 500", "3: 400x500", "3 400x500" etc.
_pair_pattern = re.compile(
    r"(?:\b(\d{1,2})\b\s*[:=\-]?\s*)?"           # opcional cantidad (1-2 dígitos) + separador
    r"(\d{2,4})\s*[x×X]\s*(\d{2,4})"             # largo x ancho
)

def _extract_pairs_from_text(texto):
    """
    Extrae tuplas (cantidad, largo, ancho) de un texto dado.
    Filtra por límites razonables.
    """
    texto = texto.replace("×", "x")
    texto = texto.replace(",", " ")
    out = []
    for m in _pair_pattern.finditer(texto):
        try:
            cant = int(m.group(1)) if m.group(1) else 1
            largo = int(m.group(2))
            ancho = int(m.group(3))
            # límites de plausibilidad (mm)
            if 30 <= largo <= 4000 and 30 <= ancho <= 4000 and 1 <= cant <= 99:
                out.append((cant, largo, ancho))
        except Exception:
            continue
    return out

# ==== Preprocesado ====
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
    # calcula ángulo usando momentos de bordes o Hough
    coords = np.column_stack(np.where(gray < 128))
    if coords.shape[0] < 10:
        return gray, 0.0
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    # rotación si la inclinación es significativa
    if abs(angle) < 1.0:
        return gray, 0.0
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle

def _preprocess(img_bgr):
    # copia local y trabajable
    img = img_bgr.copy()
    # convertir a gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # aplicar CLAHE para mejorar contraste local
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass

    # denoise ligero (bilateral preserva bordes)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)

    # intentar deskew en una copia
    deskewed, angle = _deskew_image(gray)
    gray = deskewed

    # umbral adaptativo (mejor para papel manuscrito)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 15, 8)
    # invertimos (texto oscuro sobre fondo claro -> queremos texto en negro)
    inv = 255 - th

    # morfología para unir trazos horizontales de una línea
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15,3))
    morph = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel, iterations=1)

    # retorno: imagen en gris mejorada + la máscara morfologica para detectar regiones
    return gray, morph, angle

# ==== Detección de cajas de texto mediante contornos ====
def _find_text_boxes(morph_mask):
    contours, _ = cv2.findContours(morph_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        # filtrado por área y aspecto
        area = w*h
        if area < 2000:           # area mínima (ajustable)
            continue
        if w < 60 or h < 18:      # caja demasiado estrecha/pequeña
            continue
        # posible ratio muy alargado -> ignorar si es solo una línea decorativa
        if w/h < 1.2 and h < 25:
            continue
        boxes.append((x,y,w,h,area))
    # ordenar de arriba a abajo por y
    boxes = sorted(boxes, key=lambda b: b[1])
    # fusionar cajas muy cercanas (misma línea)
    merged = []
    for b in boxes:
        if not merged:
            merged.append(b)
        else:
            x,y,w,h,area = b
            px,py,pw,ph,parea = merged[-1]
            # si verticalmente muy cerca y se solapan horizontalmente -> unir
            if (y - (py+ph)) < 18 and (x < px+pw+20 and px < x+ w + 20):
                nx = min(x,px)
                ny = min(y,py)
                nw = max(x+w, px+pw) - nx
                nh = max(y+h, py+ph) - ny
                merged[-1] = (nx, ny, nw, nh, nw*nh)
            else:
                merged.append(b)
    return merged

# ==== OCR por caja combinando varios psm y filtrando ====
def _ocr_box_text(img_bgr, box, lang="eng+spa"):
    x,y,w,h,area = box
    pad = 6
    H, W = img_bgr.shape[:2]
    x0 = max(0, x-pad); y0 = max(0, y-pad)
    x1 = min(W, x+w+pad); y1 = min(H, y+h+pad)
    roi = img_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return ""
    # convertir a PIL para pytesseract si hace falta
    pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))

    # configuraciones: whitelist + numeric bias
    base_cfg = "-c tessedit_char_whitelist=0123456789xX:= -c classify_bln_numeric_mode=1 -c user_defined_dpi=200"

    results = []
    # probar varios psm (7 = linea, 6 = bloque, 11 = sparse text)
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
    # si no hay texto, tratar ROI con binarización extra
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

    # seleccionar mejor resultado heurístico (más dígitos, formato válido)
    best = ""
    best_score = -1
    for psm, t in results:
        # score = cantidad de dígitos encontrados + presencia de 'x'
        digits = len(re.findall(r"\d", t))
        has_x = 2 if re.search(r"[xX]", t) else 0
        score = digits + has_x
        if score > best_score:
            best = t
            best_score = score
    return best

# ==== Función principal: analyze_image ====
def analyze_image(path, lang="eng+spa"):
    """
    Entrada: path (imagen)
    Salida: lista de piezas. Cada pieza = {
        "cantidad": int,
        "largo": int,
        "ancho": int,
        "cantos": {...},
        "ocr_texto": str,
        "x": int, "y": int, "w": int, "h": int
    }
    """
    _log("Analyze image:", path)
    if not os.path.exists(path):
        _log("Imagen no encontrada:", path)
        return []

    img = cv2.imread(path)
    if img is None:
        _log("cv2.imread devolvió None")
        return []

    # redimensionar para velocidad y consistencia
    img, scale = _resize_keep_aspect(img, MAX_SIDE)
    ih, iw = img.shape[:2]
    _log("imagen resized:", iw, ih, "scale", scale)

    gray, morph, angle = _preprocess(img)
    _log("deskew angle:", angle)

    boxes = _find_text_boxes(morph)
    _log("boxes detectadas:", boxes)

    piezas = []
    seen_texts = set()
    for b in boxes:
        txt = _ocr_box_text(img, b, lang=lang)
        _log("OCR caja:", b, "=>", txt)
        if not txt or len(re.sub(r"\D", "", txt)) < 2:
            # texto demasiado corto -> ignorar
            continue
        # extraer pares
        pares = _extract_pairs_from_text(txt)
        if not pares:
            # intentar combinar con texto cercano (vecinos)
            # mirar una franja vertical alrededor y concatenar OCR completo
            x,y,w,h,area = b
            # zona ampliada
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
        # si encontramos pares, creamos piezas por cada par (multiplicar si cantidad>1)
        if pares:
            for (cant, largo, ancho) in pares:
                piece = {
                    "cantidad": cant,
                    "largo": largo,
                    "ancho": ancho,
                    "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                    "ocr_texto": txt,
                    # ajustamos coordenadas a la escala original (app puede esperar px en imagen redimensionada)
                    "x": int(b[0] / scale),
                    "y": int(b[1] / scale),
                    "w": int(b[2] / scale),
                    "h": int(b[3] / scale),
                }
                # evitar duplicados por cajas solapadas
                key = f"{cant}-{largo}-{ancho}-{piece['x']}-{piece['y']}"
                if key in seen_texts:
                    continue
                seen_texts.add(key)
                piezas.append(piece)

    # fallback: si no hay piezas detectadas, intentar OCR global con regex
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

    # opcional: escribir CSV de debug si se solicita por variable de entorno
    if os.environ.get("OCR_DUMP_CSV") == "1":
        try:
            with open("resultado_despiece.csv", "w", newline="", encoding="utf-8") as f:
                wcsv = csv.writer(f)
                wcsv.writerow(["cantidad", "largo", "ancho", "x", "y", "w", "h", "texto"])
                for p in piezas:
                    wcsv.writerow([p["cantidad"], p["largo"], p["ancho"], p["x"], p["y"], p["w"], p["h"], p["ocr_texto"]])
        except Exception:
            pass

    _log("Piezas finales:", piezas)
    return piezas

# ========== Si se ejecuta como script para prueba local ==========
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ocr_rayas_tesseract.py imagen.jpg")
        sys.exit(1)
    imgpath = sys.argv[1]
    res = analyze_image(imgpath, lang="eng+spa")
    print("RESULT:", res)
