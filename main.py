from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import os

from carobot import responder  # Asegurate de tener esta función en carobot.py

# --- Cargar variables de entorno ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)

# --- Crear app Flask ---
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

# --- Handlers ---
def start(update: Update, context):
    update.message.reply_text("¡Hola! Soy Carobot.")

def handle_text(update: Update, context):
    mensaje = update.message.text
    responder(mensaje, update)  # Llama la función en carobot.py

# --- Registrar Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

# --- Ruta del Webhook ---
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


# --- Ruta de prueba (opcional) ---
@app.route("/", methods=["GET"])
def index():
    return "Carobot está funcionando", 200

# --- Ejecutar App (localmente) ---
if __name__ == "__main__":
    app.run(port=8000)
