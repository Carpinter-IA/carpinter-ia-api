# Imagen base mínima
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Paquetes necesarios en runtime:
# - Tesseract + idiomas ENG/SPA
# - Libs que necesita OpenCV (ruedas precompiladas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
 && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Instala deps de Python primero (cachea mejor)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del proyecto
COPY . .

# Tesseract data path en Debian/Ubuntu
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV PORT=5000

EXPOSE 5000

# Gunicorn en producción; 1 worker gthread para plan gratuito
CMD ["gunicorn", "-w", "1", "-k", "gthread", "-t", "120", "-b", "0.0.0.0:5000", "app:app"]
