# Usa una imagen oficial de Python 3.10
FROM python:3.10-slim

# Instala ffmpeg para procesar audios
RUN apt-get update && apt-get install -y ffmpeg

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto
COPY main /app

# Instala las dependencias
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expone el puerto (por si es necesario, aunque Telegram no lo requiere)
EXPOSE 8000

# Comando para iniciar tu bot
CMD ["python", "main.py"]
