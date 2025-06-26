# Usa una imagen oficial de Python 3.10
FROM python:3.10-slim

# Instala ffmpeg para procesar audios
RUN apt-get update && apt-get install -y ffmpeg

# Establece el directorio de trabajo
WORKDIR /app

# Copia todos los archivos del proyecto
COPY . .

# Instala las dependencias
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expone el puerto (coincide con el que usará Gunicorn)
EXPOSE 8080

# Comando para iniciar tu bot con Gunicorn (Flask WSGI)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
