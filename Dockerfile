# Imagen base mínima con Python 3.12
FROM python:3.12-slim

# Variables básicas de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instalar dependencias del sistema:
# - Tesseract + idiomas ENG/SPA
# - Librerías necesarias para OpenCV y Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    libtesseract-dev \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libjpeg62-turbo \
 && rm -rf /var/lib/apt/lists/*

# Configuración de variables para pytesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV PORT=5000

# Crear directorio de trabajo
WORKDIR /app

# Copiar dependencias Python primero (mejor cacheo)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Exponer el puerto (Render usa automáticamente $PORT)
EXPOSE 5000

# Ejecutar la app con Gunicorn (1 worker gthread, ideal para plan gratuito)
CMD ["gunicorn", "-w", "1", "-k", "gthread", "-t", "120", "-b", "0.0.0.0:5000", "app:app"]

