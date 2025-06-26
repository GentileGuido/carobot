from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI

# Cargar .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = os.getenv("VOICE_ID")

# URLs y rutas
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"
WEBHOOK_PATH = "/webhook"

# Inicializaciones
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Lógica IA
def transcribir_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return result.text
    except Exception as e:
        print("❌ Transcripción:", e)
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
        print("❌ GPT:", e)
        return "Tuve un problema generando mi respuesta."

def texto_a_voz(texto, filename="respuesta.mp3"):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVEN_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": texto,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            with open(filename, "wb") as f:
                f.write(res.content)
            return filename
        else:
            print("❌ ElevenLabs:", res.text)
            return None
    except Exception as e:
        print("❌ Eleven Error:", e)
        return None

# Bot logic
def responder(update: Update, context):
    msg = update.message
    chat_id = msg.chat_id

    if msg.voice:
        try:
            file = msg.voice.get_file()
            ogg = f"audio_{chat_id}.ogg"
            mp3 = f"audio_{chat_id}.mp3"
            file.download(ogg)
            AudioSegment.from_ogg(ogg).export(mp3, format="mp3")
            transcripcion = transcribir_audio(mp3)
            msg.reply_text(f"📜 {transcripcion}")
            respuesta = generar_respuesta(transcripcion)
            voz = texto_a_voz(respuesta)
            if voz:
                msg.reply_voice(voice=open(voz, "rb"))
            else:
                msg.reply_text(respuesta)
        except Exception as e:
            print("❌ Error en audio:", e)
            msg.reply_text("Tuve un problema con el audio.")
    elif msg.text:
        respuesta = generar_respuesta(msg.text)
        voz = texto_a_voz(respuesta)
        if voz:
            msg.reply_voice(voice=open(voz, "rb"))
        else:
            msg.reply_text(respuesta)

# Handlers
dispatcher.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 ¡Hola! Soy Carobot.")))
dispatcher.add_handler(MessageHandler(Filters.voice, responder))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, responder))

# Flask Routes
@app.route("/", methods=["GET"])
def index():
    return "✅ Carobot Webhook listo", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{RENDER_URL}{WEBHOOK_PATH}"
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
    return {"status": res.status_code, "response": res.json()}, res.status_code

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        print("❌ Error en webhook:", e)
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
