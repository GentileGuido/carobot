from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI

print("🧠 Iniciando Carobot...")

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = os.getenv("VOICE_ID")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"
WEBHOOK_PATH = "/webhook"

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ No se cargó TELEGRAM_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ No se cargó OPENAI_API_KEY")

print("✅ Variables de entorno cargadas")

# Inicializar Flask y Telegram
app = Flask(__name__)
print("✅ Flask inicializado")

bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Lógica IA
def transcribir_audio(file_path):
    print("📝 Transcribiendo audio...")
    try:
        with open(file_path, "rb") as audio_file:
            result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return result.text
    except Exception as e:
        print("❌ Error transcripción:", e)
        return "No pude entender el audio."

def generar_respuesta(texto):
    print("🤖 Generando respuesta...")
    try:
        chat = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": texto}],
            temperature=0.7
        )
        return chat.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error GPT:", e)
        return "Tuve un problema generando mi respuesta."

def texto_a_voz(texto, filename="respuesta.mp3"):
    print("🗣 Convirtiendo texto a voz...")
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVEN_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": texto,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            with open(filename, "wb") as f:
                f.write(res.content)
            return filename
        else:
            print("❌ Error ElevenLabs:", res.text)
            return None
    except Exception as e:
        print("❌ Error Eleven Exception:", e)
        return None

# Respuesta al usuario
def responder(update: Update, context):
    msg = update.message
    chat_id = msg.chat_id
    print(f"📥 Mensaje recibido de {chat_id}")

    try:
        if msg.voice:
            file = msg.voice.get_file()
            ogg = f"audio_{chat_id}.ogg"
            mp3 = f"audio_{chat_id}.mp3"
            file.download(ogg)
            AudioSegment.from_ogg(ogg).export(mp3, format="mp3")
            transcripcion = transcribir_audio(mp3)
            msg.reply_text(f"📜 {transcripcion}")
            respuesta = generar_respuesta(transcripcion)
        else:
            transcripcion = msg.text
            respuesta = generar_respuesta(transcripci_
