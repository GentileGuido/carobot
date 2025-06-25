from queue import Queue
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import os
import requests

from carobot import responder  # Asegurate que responder maneje texto y voz correctamente

# --- Cargar variables de entorno ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"
WEBHOOK_PATH = "/webhook"
bot = Bot(token=TOKEN)

# --- Iniciar Flask + Dispatcher de Telegram ---
app = Flask(__name__)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)

# --- Handlers de comandos y mensajes ---
def start(update: Update, context):
    update.message.reply_text("👋 ¡Hola! Soy Carobot. Probá escribirme o mandame un audio.")

def handle_message(update: Update, context):
    mensaje = update.message.text if update.message.text else None
    responder(mensaje, update)

# --- Registrar handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(MessageHandler(Filters.voice, handle_message))

# --- Ruta base ---
@app.route("/", methods=["GET"])
def index():
    return "✅ Carobot Webhook OK", 200

# --- Ruta para activar Webhook manualmente ---
@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    response = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    )
    return {"status": response.status_code, "response": response.json()}, response.status_code

# --- Ruta para eliminar Webhook manualmente ---
@app.route("/deletewebhook", methods=["GET"])
def delete_webhook():
    response = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    return {"status": response.status_code, "response": response.json()}, response.status_code

# --- Ruta FIJA para recibir updates desde Telegram ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

# --- Ejecutar Flask localmente (opcional) ---
if __name__ == "__main__":
    print("✅ Carobot se está ejecutando en modo Webhook.")
    app.run(host="0.0.0.0", port=8000)
