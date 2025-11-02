FROM python:3.12-slim

# Instalar dependencias del sistema + Tesseract (con idioma español)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copiar el código al contenedor
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

# Render usa PORT, Flask debe escuchar en 0.0.0.0:$PORT
ENV PORT=8000
EXPOSE 8000

CMD ["python", "app.py"]
