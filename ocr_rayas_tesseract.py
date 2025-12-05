# -*- coding: utf-8 -*-
"""
OCR helper para Carpinter-IA
Archivo único: ocr_rayas_tesseract.py

Funciones públicas:
- run_ocr_and_get_pieces(image_path, debug_overlay=None, lang="eng+spa")
    -> devuelve (piezas, width, height)
    -> guarda debug_overlay.png en /tmp si detecta cajas (solo si ruta destino != input)
    -> registra /tmp/last_result.json (no necesario, app.py puede usarlo)

Hecho robusto para servidores tipo Render (Linux) y Windows local.
"""

import os
import re
import json
import time
import tempfile
import platform
import shutil
import logging

import cv2
import numpy as np
import pytesseract

# --------------------- Config/entorno Tesseract portable ---------------------
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

# --------------------- Logging (simple) ---------------------
LOG_LEVEL = os.environ.get("OCR_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="[OCR %(levelname)s] %(message)s")
logger = logging.getLogger("carpinter_ocr")

# --------------------- Ajustes OCR/transformaciones ---------------------
MAX_SIDE = int(os.environ.get("OCR_MAX_SIDE", 1400))
OCR_TIMEOUT_LINE = int(os.environ.get("OCR_TIMEOUT_LINE", 12))
OCR_TIMEOUT_GLOBAL = int(os.environ.get("OCR_TIMEOUT_GLOBAL", 30))

# --------------------- Paths por defecto ---------------------
DEBUG_OVERLAY_DEFAULT = "/tmp/debug_overlay.png"
LAST_JSON_PATH = "/tmp/last_result.json"

# --------------------- Funciones auxiliares ---------------------
def _extract_pairs_from_text(texto):
    texto = texto.replace("×", "x").replace("X", "x")
    texto = re.sub(r"[=\:\-]+", " ", texto)
    patron = re.compile(r"(?:\b(\d{1,2})\b\s+)?(\d{2,4})\s*[x]\s*(\d{2,4})")
    out = []
    for m in patron.finditer(texto):
        cant = int(m.group(1)) if m.group(1) else 1
        largo = int(m.group(2))
        ancho = int(m.group(3))
        if 40 <= largo <= 4000 and 40 <= ancho <= 4000:
            out.append((cant, largo, ancho))
    return out


def _find_text_rows(img):
    try:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception:
        return []
    thr = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 7)
    inv = cv2.bitwise_not(thr)
    hproj = np.sum(inv // 255, axis=1)
    h = inv.shape[0]
    umbral = max(8, int(inv.shape[1] * 0.02))
    filas, en_banda, y0 = [], False, 0
    for y in range(h):
        if hproj[y] > umbral and not en_banda:
            en_banda, y0 = True, y
        elif hproj[y] <= umbral and en_banda:
            en_banda = False
            y1 = y
            if y1 - y0 >= 12:
                filas.append(img[y0:y1, :])
    if en_banda and h - y0 >= 12:
        filas.append(img[y0:h, :])
    return filas


def _ocr_text_line(roi, lang="eng+spa"):
    g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if g.shape[0] < 60:
        g = cv2.resize(g, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    g = cv2.medianBlur(g, 3)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cfg = (
        "--oem 3 --psm 7 "
        "-c tessedit_char_whitelist=0123456789xX "
        "-c classify_bln_numeric_mode=1 "
        "-c user_defined_dpi=180"
    )
    try:
        txt = pytesseract.image_to_string(bw, lang=lang, config=cfg, timeout=OCR_TIMEOUT_LINE)
    except RuntimeError:
        return ""
    txt = re.sub(r"[^\dxX ]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _ocr_full_image(img, lang="eng+spa"):
    piezas = []
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)

    variantes = []
    _, otsu = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variantes.append(otsu)
    variantes.append(cv2.bitwise_not(otsu))

    base_cfg = (
        "--oem 3 -c tessedit_char_whitelist=0123456789xX=:-/ "
        "-c classify_bln_numeric_mode=1 "
        "-c user_defined_dpi=180"
    )

    textos = []
    for v in variantes:
        for psm in (6, 11, 7):
            cfg = f"{base_cfg} --psm {psm}"
            try:
                t = pytesseract.image_to_string(v, lang=lang, config=cfg, timeout=OCR_TIMEOUT_GLOBAL)
                textos.append(t)
            except RuntimeError:
                logger.debug(f"Fallback global OCR psm {psm} timeout")
                continue

    bruto = re.sub(r"[^\d xX]", " ", " ".join(textos))
    for (cant, largo, ancho) in _extract_pairs_from_text(bruto):
        piezas.append({
            "cantidad": cant, "largo": largo, "ancho": ancho,
            "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
            "ocr_texto": f"{cant} {largo}x{ancho}"
        })
    return piezas


def _detect_text_boxes(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = cv2.bitwise_not(th)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    morphed = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    h, w = img.shape[:2]
    for c in contours:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        if hh >= 12 and ww >= 40 and area >= 2000 and ww < w * 0.98:
            boxes.append((x, y, ww, hh, area))
    boxes = sorted(boxes, key=lambda b: b[1])
    return boxes


def _save_debug_overlay(img, boxes, out_path):
    if not boxes:
        return None
    vis = img.copy()
    for (x, y, w, h, _) in boxes:
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 2)
        text = f"{x}x{y} {w}x{h}"
        cv2.putText(vis, text, (x + 4, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

    try:
        tmp_out = out_path
        if os.path.exists(out_path):
            fd, tmp_name = tempfile.mkstemp(suffix=os.path.splitext(out_path)[1], dir=os.path.dirname(out_path) or "/tmp")
            os.close(fd)
            tmp_out = tmp_name
        cv2.imwrite(tmp_out, vis)
        if tmp_out != out_path:
            try:
                shutil.move(tmp_out, out_path)
            except Exception:
                shutil.copy(tmp_out, out_path)
                os.unlink(tmp_out)
        return out_path
    except Exception as e:
        logger.warning(f"No se pudo guardar overlay: {e}")
        return None


def _write_last_result_json(result_obj, path=LAST_JSON_PATH):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result_obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.debug(f"No se pudo escribir last_result.json: {e}")


def analyze_image(image_path, lang="eng+spa", dump_csv=False):
    logger.info(f"Analyze image: {image_path}")
    start = time.time()

    img = cv2.imread(image_path)
    if img is None:
        logger.error("No se pudo leer la imagen.")
        return [], 0, 0

    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:
        esc = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * esc), int(h * esc)))
        logger.debug(f"Imagen reducida a {img.shape[1]}x{img.shape[0]}")

    boxes = _detect_text_boxes(img)
    piezas = []
    if boxes:
        logger.info(f"Detectadas {len(boxes)} cajas")
        for i, (x, y, ww, hh, _) in enumerate(boxes, start=1):
            pad_x = int(ww * 0.03) + 2
            pad_y = int(hh * 0.15) + 2
            x0 = max(0, x - pad_x)
            y0 = max(0, y - pad_y)
            x1 = min(img.shape[1], x + ww + pad_x)
            y1 = min(img.shape[0], y + hh + pad_y)
            roi = img[y0:y1, x0:x1]
            filas = _find_text_rows(roi)
            if filas:
                for j, r in enumerate(filas, 1):
                    t = _ocr_text_line(r, lang=lang)
                    if not t:
                        continue
                    logger.debug(f"[OCR][box {i} fila {j}] '{t}'")
                    for (cant, largo, ancho) in _extract_pairs_from_text(t):
                        piezas.append({"cantidad": cant, "largo": largo, "ancho": ancho,
                                       "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                                       "ocr_texto": f"{cant} {largo}x{ancho}"})
            else:
                for psm in (7, 6):
                    cfg = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789xX -c classify_bln_numeric_mode=1"
                    try:
                        t = pytesseract.image_to_string(roi, lang=lang, config=cfg, timeout=OCR_TIMEOUT_LINE)
                    except RuntimeError:
                        t = ""
                    t = re.sub(r"[^\dxX ]", " ", t)
                    t = re.sub(r"\s+", " ", t).strip()
                    if t:
                        logger.debug(f"[OCR][box {i} psm{psm}] '{t}'")
                        for (cant, largo, ancho) in _extract_pairs_from_text(t):
                            piezas.append({"cantidad": cant, "largo": largo, "ancho": ancho,
                                           "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                                           "ocr_texto": f"{cant} {largo}x{ancho}"})
                        break

    if not piezas:
        logger.info("No se detectaron piezas por cajas; probando OCR global")
        piezas = _ocr_full_image(img, lang=lang)

    # Guardar overlay seguro (solo si hay cajas)
    try:
        overlay_out = DEBUG_OVERLAY_DEFAULT
        input_abs = os.path.abspath(image_path)
        if os.path.abspath(overlay_out) == input_abs:
            overlay_out = os.path.join("/tmp", f"debug_overlay_{int(time.time())}.png")
        saved = _save_debug_overlay(img, boxes, overlay_out)
        if saved:
            logger.debug(f"Overlay guardado en {saved}")
    except Exception as e:
        logger.debug(f"No se pudo generar overlay: {e}")

    # Guardar last_result.json
    try:
        result_obj = {
            "image_height": int(h),
            "image_width": int(w),
            "meta": {"image_path": image_path},
            "piezas": piezas
        }
        _write_last_result_json(result_obj, path=LAST_JSON_PATH)
    except Exception as e:
        logger.debug(f"Error guardando last_result.json: {e}")

    logger.info(f"Análisis finalizado en {int((time.time()-start)*1000)} ms. Piezas: {len(piezas)}")
    return piezas, img.shape[1], img.shape[0]


def run_ocr_and_get_pieces(image_path, debug_overlay=None, lang="eng+spa"):
    """
    Public API expected by app.py.
    If debug_overlay is provided (path), copy the internal /tmp/debug_overlay.png to that path.
    Returns (piezas, width, height).
    """
    try:
        piezas, w, h = analyze_image(image_path, lang=lang)
        # Si el usuario pidió un path para el overlay, copiarlo si existe
        internal_overlay = DEBUG_OVERLAY_DEFAULT
        if debug_overlay and os.path.exists(internal_overlay):
            try:
                # si rutas coinciden, saltar copia
                if os.path.abspath(debug_overlay) != os.path.abspath(internal_overlay):
                    # asegurar directorio destino
                    os.makedirs(os.path.dirname(debug_overlay), exist_ok=True)
                    shutil.copy(internal_overlay, debug_overlay)
            except Exception as e:
                logger.debug(f"No se pudo copiar overlay a {debug_overlay}: {e}")
        return piezas, w, h
    except Exception as e:
        logger.exception(f"run_ocr_and_get_pieces error: {e}")
        return [], 0, 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python ocr_rayas_tesseract.py <imagen>")
        sys.exit(1)
    imgp = sys.argv[1]
    os.environ["OCR_DEBUG"] = "1"
    pcs, W, H = run_ocr_and_get_pieces(imgp)
    print("RESULT:", pcs)
