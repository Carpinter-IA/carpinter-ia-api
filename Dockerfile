# Imagen base
FROM python:3.12-slim

# Tesseract + idiomas + dependencias de OpenCV
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    libtesseract-dev \
    libleptonica-dev \
    libglib2.0-0 \
    libgl1 \
    libjpeg62-turbo \
 && rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Entorno
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV PYTHONUNBUFFERED=1

# Gunicorn en Render
EXPOSE 5000
CMD ["gunicorn","-w","2","-b","0.0.0.0:5000","app:app"]
