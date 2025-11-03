# Imagen base con Python y Tesseract
FROM python:3.12-slim

# Instalar dependencias de Tesseract y utilidades
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    && apt-get clean

# Crear y usar directorio de trabajo
WORKDIR /app

# Copiar todos los archivos al contenedor
COPY . .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Exponer el puerto
EXPOSE 5000

# Comando para iniciar el servidor Flask (usando gunicorn, recomendado por Render)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

