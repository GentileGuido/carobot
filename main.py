from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os, requests
from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI

# --- Cargar variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = os.getenv("VOICE_ID")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://carobot.onrender.com")
WEBHOOK_PATH = "/webhook"

# --- Inicializar servicios ---
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Funciones de IA ---
def transcribir_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            result = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        return result.text
    except Exception as e:
        print("❌ Error transcripción:", e)
        return "No pude entender el audio."

def generar_respuesta(texto):
    try:
        chat = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": texto}],
            temperature=0.7
        )
        return chat.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error GPT:", e)
        return "Tuve un problema al pensar mi respuesta."

def texto_a_voz(texto, filename="respuesta.mp3"):
    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}",
            headers={
                "xi-api-key": ELEVEN_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": texto,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
        )
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
        else:
            print("❌ ElevenLabs error:", response.text)
            return None
    except Exception as e:
        print("❌ Error en texto a voz:", e)
        return None

# --- Lógica de respuesta ---
def responder(update: Update):
    chat_id = update.message.chat_id
    texto = update.message.text

    if update.message.voice:
        try:
            voice_file = update.message.voice.get_file()
            ogg = f"voz_{chat_id}.ogg"
            mp3 = f"voz_{chat_id}.mp3"
            voice_file.download(ogg)
            AudioSegment.from_ogg(ogg).export(mp3, format="mp3")
            texto = transcribir_audio(mp3)
            update.message.reply_text(f"📜 {texto}")
        except Exception as e:
            print("❌ Error audio:", e)
            update.message.reply_text("Error procesando el audio.")
            return

    if texto:
        respuesta = generar_respuesta(texto)
        archivo = texto_a_voz(respuesta)
        if archivo:
            update.message.reply_voice(voice=open(archivo, "rb"))
        else:
            update.message.reply_text(respuesta)

# --- Telegram handlers ---
def start(update: Update, context): update.message.reply_text("👋 Soy Carobot. Mandame texto o audio.")
def handle(update: Update, context): responder(update)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
dispatcher.add_handler(MessageHandler(Filters.voice, handle))

# --- Rutas web ---
@app.route("/", methods=["GET"])
def index(): return "✅ Carobot Webhook Activo", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": webhook_url})
    return {"status": res.status_code, "response": res.json()}

@app.route("/deletewebhook", methods=["GET"])
def delete_webhook():
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
    return {"status": res.status_code, "response": res.json()}

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

if __name__ == "__main__":
    print("🔁 Ejecutando localmente")
    app.run(host="0.0.0.0", port=8000)
