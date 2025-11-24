# =============== BASE IMAGE ===============
FROM python:3.12-slim

# =============== SISTEMA (INSTALAR TESSERACT) ===============
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        libtesseract-dev \
        libleptonica-dev \
        pkg-config \
        build-essential \
        poppler-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# =============== DIRECTORIO DEL APP ===============
WORKDIR /app

# =============== DEPENDENCIAS PYTHON ===============
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# =============== COPIAR CÓDIGO ===============
COPY . /app/

# =============== PUERTO PARA RENDER ===============
ENV PORT=5000

# Render asigna dinámicamente el puerto, Flask debe respetarlo
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
