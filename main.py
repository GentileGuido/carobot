from queue import Queue
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import os
import requests

from carobot import responder  # Asegurate de tener esta función en carobot.py

# --- Cargar variables de entorno ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)

# --- Crear app Flask ---
app = Flask(__name__)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=0, use_context=True)

# --- Handlers ---
def start(update: Update, context=None):
    update.message.reply_text("¡Hola! Soy Carobot.")

def handle_text(update: Update, context=None):
    mensaje = update.message.text
    responder(mensaje, update)  # Llama a la función en carobot.py

# --- Registrar Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(MessageHandler(Filters.voice, handle_text))  # Agregamos soporte a audio

# --- Ruta raíz (opcional) ---
@app.route("/", methods=["GET"])
def index():
    return "Carobot está funcionando", 200

# --- Ruta para activar el Webhook ---
@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://carobot.onrender.com/{TOKEN}"
    response = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    )
    return {
        "status": response.status_code,
        "response": response.json()
    }, response.status_code

# --- Ruta para eliminar el Webhook ---
@app.route("/deletewebhook", methods=["GET"])
def delete_webhook():
    response = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    return {
        "status": response.status_code,
        "response": response.json()
    }, response.status_code

# --- Ruta que recibe updates desde Telegram ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

# --- Ejecutar App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
