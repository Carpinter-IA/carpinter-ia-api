# -*- coding: utf-8 -*-
import os, re, sys, csv, argparse
import cv2, numpy as np, pytesseract
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject

# ==================== CONFIGURACIÓN TESSERACT ====================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"
os.environ.pop("TESSDATA_PREFIX", None)
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

# === Ajustes de robustez OCR ===
MAX_SIDE = 1400
OCR_TIMEOUT_LINE = 12
OCR_TIMEOUT_GLOBAL = 30
# ================================================================


# ==================== FUNCIONES OCR ====================
def _extract_pairs_from_text(texto):
    texto = texto.replace("×", "x")
    texto = re.sub(r"[=\:\-]+", " ", texto)
    patron = re.compile(r"(?:\b(\d{1,2})\b\s+)?(\d{2,4})\s*[xX]\s*(\d{2,4})")
    out = []
    for m in patron.finditer(texto):
        cant = int(m.group(1)) if m.group(1) else 1
        largo = int(m.group(2))
        ancho = int(m.group(3))
        if 40 <= largo <= 4000 and 40 <= ancho <= 4000:
            out.append((cant, largo, ancho))
    return out


def _find_text_rows(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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
        for psm in (6, 11):
            cfg = f"{base_cfg} --psm {psm}"
            try:
                t = pytesseract.image_to_string(v, lang=lang, config=cfg, timeout=OCR_TIMEOUT_GLOBAL)
                textos.append(t)
            except RuntimeError:
                print(f"[DEBUG] Fallback global timeout con psm {psm}, continúo…")
                continue

    bruto = re.sub(r"[^\d xX]", " ", " ".join(textos))
    for (cant, largo, ancho) in _extract_pairs_from_text(bruto):
        piezas.append({
            "cantidad": cant, "largo": largo, "ancho": ancho,
            "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
            "ocr_texto": f"{cant} {largo}x{ancho}"
        })
    return piezas


# ==================== PDF MAESTRO ====================
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject, ArrayObject

def exportar_pdf_maestro(
    piezas,
    maestro_path="Carpinter-IA_Despiece.pdf",
    salida_path="resultado_despiece.pdf",
):
    if not os.path.exists(maestro_path):
        print(f"⚠️ No se encontró el PDF maestro: {maestro_path}")
        return

    reader = PdfReader(maestro_path)
    writer = PdfWriter()

    # Copiamos todas las páginas
    for page in reader.pages:
        writer.add_page(page)

    # ===== Copiar /AcroForm (si el maestro lo tiene) =====
    root_reader = reader.trailer["/Root"]
    root_writer = writer._root_object

    if "/AcroForm" in root_reader:
        # Clonamos el diccionario de AcroForm del maestro al writer
        acro = root_reader["/AcroForm"]
        # Importante: asegurarnos de que el objeto esté dentro del writer
        root_writer.update({NameObject("/AcroForm"): writer._add_object(acro)})
    else:
        # Si el PDF no trae AcroForm, lo creamos con /Fields vacío
        acro = DictionaryObject()
        acro.update({NameObject("/Fields"): ArrayObject()})
        root_writer.update({NameObject("/AcroForm"): writer._add_object(acro)})

    # Marcar NeedAppearances para que se vean los valores y checkboxes
    root_writer["/AcroForm"].update({
        NameObject("/NeedAppearances"): BooleanObject(True)
    })

    # ===== Rellenar campos de las primeras 15 filas =====
    campos = {}
    for i, p in enumerate(piezas[:15], 1):
        campos[f"REF. TABLERO_{i}"] = "TABLERO"
        campos[f"LARGO (mm)_{i}"]   = str(p["largo"])
        campos[f"ANCHO (mm)_{i}"]   = str(p["ancho"])
        campos[f"ESPESOR (mm)_{i}"] = "16"
        campos[f"CANTIDAD_{i}"]     = str(p["cantidad"])
        # Si tienes checkboxes y quieres marcarlos por defecto, podrías hacer:
        # campos[f"canto_L1_{i}"] = "On" if p["cantos"].get("L1") else "Off"
        # ... idem L2, A1, A2

    # Actualizamos los valores sobre la primera página (donde están los campos)
    writer.update_page_form_field_values(writer.pages[0], campos)

    with open(salida_path, "wb") as f:
        writer.write(f)

    print(f"✅ PDF maestro rellenado y guardado como '{salida_path}'.")



# ==================== FLUJO PRINCIPAL ====================
def analyze_image(path, lang="eng+spa"):
    print("[DEBUG] tesseract:", pytesseract.get_tesseract_version())
    print("[DEBUG] langs disponibles:", pytesseract.get_languages(config=""))
    print(">> OCR en progreso...")

    img = cv2.imread(path)
    if img is None:
        print("No se pudo leer la imagen.")
        return []

    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:
        esc = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * esc), int(h * esc)))
        print(f"[DEBUG] Imagen reducida a {img.shape[1]}x{img.shape[0]}")

    filas = _find_text_rows(img)
    piezas = []
    if filas:
        print(f"[DEBUG] Detectadas {len(filas)} filas de texto")
        for i, roi in enumerate(filas, 1):
            t = _ocr_text_line(roi, lang=lang)
            if not t:
                continue
            print(f"[DEBUG OCR][fila {i}] {t}")
            for (cant, largo, ancho) in _extract_pairs_from_text(t):
                piezas.append({"cantidad": cant, "largo": largo, "ancho": ancho,
                               "cantos": {"L1": False, "L2": False, "A1": False, "A2": False},
                               "ocr_texto": f"{cant} {largo}x{ancho}"})

    if not piezas:
        print("[DEBUG] Fallback a OCR global…")
        piezas = _ocr_full_image(img, lang=lang)

    print("\n[RESULTADO FINAL]")
    if piezas:
        for p in piezas:
            print(p)
        with open("resultado_despiece.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cantidad", "largo", "ancho"])
            for p in piezas:
                w.writerow([p["cantidad"], p["largo"], p["ancho"]])
        print("✅ Archivo guardado como 'resultado_despiece.csv'")
        exportar_pdf_maestro(piezas)
    else:
        print("⚠️ No se detectaron piezas válidas tras normalizar.")
    return piezas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagen", help="Imagen con medidas escritas (ej: Medidas2.jpeg)")
    ap.add_argument("--lang", default="eng+spa", help="Idiomas de OCR (ej: eng+spa)")
    args = ap.parse_args()
    analyze_image(args.imagen, args.lang)


if __name__ == "__main__":
    main()

