# Usa una imagen oficial de Python 3.10
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto
COPY . .

# Instala las dependencias
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expone el puerto (por si es necesario, aunque Telegram no lo requiere)
EXPOSE 8000

# Comando para iniciar tu bot
CMD ["bash", "start.sh"]
