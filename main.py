from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
import requests
import os

# VARIABLES de entorno desde Railway
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
    ELEVEN_VOICE_ID = os.environ["VOICE_ID"]
    RENDER_URL = os.environ.get("RAILWAY_PUBLIC_URL", "https://carobot.up.railway.app")
except KeyError as e:
    print(f"❌ Faltan variables de entorno: {e}")
    exit(1)

WEBHOOK_PATH = "/webhook"

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

print("🧠 Iniciando Carobot...")

@app.route("/", methods=["GET"])
def index():
    print("📡 GET /")
    return "✅ Carobot listo", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{RENDER_URL}{WEBHOOK_PATH}"
    response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
    print("🔧 Set Webhook:", response.status_code, response.text)
    return {"status": response.status_code, "response": response.json()}

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        print("❌ Error en webhook:", e)
    return "ok", 200

def start(update, context):
    update.message.reply_text("👋 ¡Hola! Soy Carobot.")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, start))  # Para probar texto

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    print(f"🚀 Lanzando Carobot en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
