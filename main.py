print("🔥 MAIN.PY ESTÁ SIENDO EJECUTADO 🔥")

from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
import os
import requests
import openai
from pydub import AudioSegment
import uuid

# 🔐 Claves desde entorno Railway
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
    ELEVEN_VOICE_ID = os.environ["VOICE_ID"]
    RENDER_URL = os.environ.get("RAILWAY_PUBLIC_URL", "https://carobot.up.railway.app")
except KeyError as e:
    print(f"❌ ERROR: Falta variable de entorno: {e}")
    exit(1)

WEBHOOK_PATH = "/webhook"
openai.api_key = OPENAI_API_KEY

# ✅ Inicializar Flask y Telegram bot
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

print("🧠 Iniciando Carobot...")

# 🔧 Comandos de Telegram
def start(update, context):
    update.message.reply_text("👋 ¡Hola! Soy Carobot. Mandame un audio o mensaje de texto.")

dispatcher.add_handler(CommandHandler("start", start))

# ✉️ Mensaje de texto
def handle_text(update, context):
    user_text = update.message.text
    reply = get_openai_response(user_text)
    audio = generate_elevenlabs_audio(reply)
    if audio:
        context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
    else:
        update.message.reply_text(reply)

dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

# 🔊 Mensaje de voz
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

dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice))

# 🎤 Transcripción de audio con OpenAI Whisper
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"]

# 💬 Respuesta de texto con ChatGPT
def get_openai_response(prompt):
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Sos Carobot, sensible, empática y muy humana."},
                      {"role": "user", "content": prompt}]
        )
        return res.choices[0].message["content"]
    except Exception as e:
        print("❌ Error con OpenAI:", e)
        return "No pude procesar tu mensaje."

# 🗣️ Generación de audio con ElevenLabs
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

# 🌐 Rutas web
@app.route("/", methods=["GET"])
def index():
    return "Carobot online", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{RENDER_URL}{WEBHOOK_PATH}"
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

# ✅ Para Gunicorn
if __name__ != "__main__":
    gunicorn_app = app
else:
    PORT = int(os.environ.get("PORT", 8080))
    print(f"🚀 Lanzando localmente en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)

# Alias para Gunicorn
app = app
