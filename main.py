
print("🔥 MAIN.PY ESTÁ SIENDO EJECUTADO 🔥")

from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
import openai
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
    print(f"❌ ERROR: Falta variable de entorno: {e}")
    exit(1)

openai.api_key = OPENAI_API_KEY
WEBHOOK_PATH = "/webhook"

# ✅ Inicializar Flask y Telegram bot
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)

print("🧠 Iniciando Carobot...")

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
        print(f"❌ Error guardando en memoria: {e}")

# 💬 Respuesta con ChatGPT
SYSTEM_PROMPT = "Sos Carobot, sensible, empática y muy humana. Recordá lo que la persona dice para conectar mejor."

def get_openai_response(prompt):
    try:
        print("📤 Enviando a OpenAI:", prompt)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages
        )
        content = res.choices[0].message["content"]
        guardar_en_memoria(prompt, content)
        return content
    except Exception as e:
        print("❌ Error con OpenAI:", e)
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
            print("❌ Error ElevenLabs:", response.status_code, response.text)
    except Exception as e:
        print("❌ Excepción ElevenLabs:", e)
    return None

# 🎤 Whisper
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"]

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
        print("📝 Transcripción:", transcript)
        reply = get_openai_response(transcript)
        audio = generate_elevenlabs_audio(reply)
        if audio:
            context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
        else:
            update.message.reply_text(reply)
    except Exception as e:
        print(f"❌ Error procesando audio: {e}")
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
    print("🔧 Webhook:", res.status_code, res.text)
    return {"status": res.status_code, "response": res.json()}

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        print(f"❌ Error procesando webhook: {e}")
    return "ok", 200

# 🔁 Gunicorn
if __name__ != "__main__":
    gunicorn_app = app
else:
    PORT = int(os.environ.get("PORT", 8080))
    print(f"🚀 Lanzando localmente en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
