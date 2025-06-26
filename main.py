import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
from openai import OpenAI
from pydub import AudioSegment
import uuid
import json
import datetime

# 🔐 Variables de entorno (adaptado a Railway)
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
    ELEVEN_VOICE_ID = os.environ["VOICE_ID"]
    PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "https://carobot-production.up.railway.app")
except KeyError as e:
    logging.critical(f"Falta variable de entorno: {e}")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)
WEBHOOK_PATH = "/webhook"

# 🔁 Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ Inicializar Flask y Telegram bot
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)

logging.info("Iniciando Carobot...")

# 🧠 Memoria emocional
MEMORIA_PATH = "memoria.json"

def guardar_en_memoria(entrada, respuesta):
    try:
        memoria = []
        if os.path.exists(MEMORIA_PATH):
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                memoria = json.load(f)

        memoria.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "entrada": entrada,
            "respuesta": respuesta
        })

        with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Error guardando en memoria: {e}")

# 💬 Respuesta con ChatGPT
SYSTEM_PROMPT = "Sos Carobot, sensible, empática y muy humana. Recordá lo que la persona dice para conectar mejor."

def get_openai_response(prompt):
    try:
        logging.info(f"Enviando a OpenAI: {prompt}")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        res = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        content = res.choices[0].message.content
        guardar_en_memoria(prompt, content)
        return content
    except Exception as e:
        logging.error(f"Error con OpenAI: {e}")
        return "No pude procesar tu mensaje."

# 🗣️ ElevenLabs
def generate_elevenlabs_audio(text):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVEN_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, headers=headers, json=data)
        if response.ok:
            file_path = f"/tmp/{uuid.uuid4()}.mp3"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        else:
            logging.error(f"Error ElevenLabs: {response.status_code} {response.text}")
    except Exception as e:
        logging.exception("Excepción ElevenLabs")
    return None

# 🎤 Whisper
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcript.text

# 📥 Texto
def handle_text(update, context):
    user_text = update.message.text
    reply = get_openai_response(user_text)
    audio = generate_elevenlabs_audio(reply)
    if audio:
        context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
    else:
        update.message.reply_text(reply)

# 📥 Voz
def handle_voice(update, context):
    file = context.bot.get_file(update.message.voice.file_id)
    ogg_path = f"/tmp/{uuid.uuid4()}.ogg"
    mp3_path = ogg_path.replace(".ogg", ".mp3")
    file.download(ogg_path)

    try:
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(mp3_path, format="mp3")
        transcript = transcribe_audio(mp3_path)
        logging.info(f"Transcripción: {transcript}")
        reply = get_openai_response(transcript)
        audio = generate_elevenlabs_audio(reply)
        if audio:
            context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
        else:
            update.message.reply_text(reply)
    except Exception as e:
        logging.exception("Error procesando audio")
        update.message.reply_text("Hubo un problema procesando tu audio.")

# ✅ Handlers
dispatcher.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 ¡Hola! Soy Carobot.")))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice))

# 🌐 Rutas web
@app.route("/", methods=["GET"])
def index():
    return "Carobot online", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
    logging.info(f"Webhook manual: {res.status_code} {res.text}")
    return {"status": res.status_code, "response": res.json()}

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        logging.exception("Error procesando webhook")
    return "ok", 200

# 🔀 Auto-setear webhook en Railway
if os.environ.get("RAILWAY_ENVIRONMENT") == "production":
    try:
        url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
        res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
        logging.info(f"Webhook auto-seteado: {res.status_code} {res.text}")
    except Exception as e:
        logging.exception("Error seteando webhook automáticamente")

# 🚀 Lanzamiento local
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    logging.info(f"Lanzando localmente en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
