from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
from dotenv import load_dotenv
from pydub import AudioSegment
import openai

# --- Cargar variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"
WEBHOOK_PATH = "/webhook"

openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_TOKEN)

# --- Flask + Telegram ---
app = Flask(__name__)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)

# --- Funciones de IA ---
def transcribir_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        print("❌ Error al transcribir:", e)
        return "Lo siento, no pude entender el audio."

def generar_respuesta(texto):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": texto}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error al generar respuesta:", e)
        return "Tuve un problema al pensar mi respuesta."

def texto_a_voz(texto, filename="respuesta.mp3"):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"}
        data = {
            "text": texto,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
        else:
            print("❌ Error ElevenLabs:", response.text)
            return None
    except Exception as e:
        print("❌ Error en ElevenLabs:", e)
        return None

# --- Función principal de respuesta ---
def responder(update: Update):
    mensaje = update.message.text if update.message.text else None
    chat_id = update.message.chat_id

    if update.message.voice:
        try:
            voice_file = update.message.voice.get_file()
            ogg_path = f"audio_{chat_id}.ogg"
            mp3_path = f"audio_{chat_id}.mp3"
            voice_file.download(ogg_path)
            AudioSegment.from_ogg(ogg_path).export(mp3_path, format="mp3")
            texto_transcrito = transcribir_audio(mp3_path)
            update.message.reply_text(f"📜 {texto_transcrito}")
            respuesta = generar_respuesta(texto_transcrito)
            archivo_voz = texto_a_voz(respuesta)
            if archivo_voz:
                update.message.reply_voice(voice=open(archivo_voz, "rb"))
            else:
                update.message.reply_text(respuesta)
        except Exception as e:
            print("❌ Error en voz:", e)
            update.message.reply_text("Tuve un problema con el audio.")
    elif mensaje:
        respuesta = generar_respuesta(mensaje)
        archivo_voz = texto_a_voz(respuesta)
        if archivo_voz:
            update.message.reply_voice(voice=open(archivo_voz, "rb"))
        else:
            update.message.reply_text(respuesta)

# --- Handlers Telegram ---
def start(update: Update, context): update.message.reply_text("👋 ¡Hola! Soy Carobot. Probá escribirme o mandame un audio.")
def handle(update: Update, context): responder(update)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
dispatcher.add_handler(MessageHandler(Filters.voice, handle))

# --- Web Server ---
@app.route("/", methods=["GET"])
def index(): return "✅ Carobot Webhook OK", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}")
    return {"status": response.status_code, "response": response.json()}, response.status_code

@app.route("/deletewebhook", methods=["GET"])
def delete_webhook():
    response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
    return {"status": response.status_code, "response": response.json()}, response.status_code

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

if __name__ == "__main__":
    print("✅ Carobot activo")
    app.run(host="0.0.0.0", port=8000)
