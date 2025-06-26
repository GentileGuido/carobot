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

# 🔐 Variables de entorno
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
    ELEVEN_VOICE_ID = os.environ["VOICE_ID"]
    PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "https://carobot-production.up.railway.app")
except KeyError as e:
    logging.critical(f"❌ Falta variable de entorno: {e}")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)
WEBHOOK_PATH = "/webhook"

# ⟳ Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ Flask y Telegram bot
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)

logging.info("🧠 Iniciando Carobot...")

# 🧠 Memoria emocional y hechos
MEMORIA_PATH = "memoria.json"
HECHOS_PATH = "hechos.json"

SYSTEM_PROMPT = (
    "Sos Carobot, una inteligencia emocional y sensible. Respondés en un tono humano y cercano, "
    "pero de forma breve y clara. No repetís frases hechas ni te extendés innecesariamente."
)

def guardar_en_memoria(entrada, respuesta):
    try:
        memoria = []
        if os.path.exists(MEMORIA_PATH):
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                try:
                    memoria = json.load(f)
                    if not isinstance(memoria, list):
                        memoria = []
                except json.JSONDecodeError:
                    memoria = []

        memoria.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "entrada": entrada,
            "respuesta": respuesta
        })

        with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
        logging.info("📝 Interacción guardada en memoria.")
    except Exception as e:
        logging.warning(f"❌ Error guardando en memoria: {e}")

def get_openai_response(prompt):
    try:
        logging.info(f"📤 Enviando a OpenAI: {prompt}")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if os.path.exists(HECHOS_PATH):
            with open(HECHOS_PATH, "r", encoding="utf-8") as f:
                try:
                    hechos = json.load(f)
                    if isinstance(hechos, list):
                        for h in hechos[-20:]:
                            messages.append({"role": "system", "content": f"Recordá esto: {h['hecho']}"})
                except Exception as e:
                    logging.warning(f"⚠️ Error leyendo hechos: {e}")

        if os.path.exists(MEMORIA_PATH):
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                try:
                    memoria = json.load(f)
                    if isinstance(memoria, list):
                        for item in memoria[-1000:]:
                            messages.append({"role": "user", "content": item["entrada"]})
                            messages.append({"role": "assistant", "content": item["respuesta"]})
                except Exception as e:
                    logging.warning(f"⚠️ Error leyendo memoria: {e}")

        messages.append({"role": "user", "content": prompt})
        res = client.chat.completions.create(model="gpt-4", messages=messages)
        content = res.choices[0].message.content
        guardar_en_memoria(prompt, content)
        return content
    except Exception as e:
        logging.error(f"❌ Error con OpenAI: {e}")
        return "No pude procesar tu mensaje."

def guardar_hecho(texto):
    try:
        hechos = []
        if os.path.exists(HECHOS_PATH):
            with open(HECHOS_PATH, "r", encoding="utf-8") as f:
                hechos = json.load(f)
                if not isinstance(hechos, list):
                    hechos = []
        hechos.append({"timestamp": datetime.datetime.now().isoformat(), "hecho": texto})
        with open(HECHOS_PATH, "w", encoding="utf-8") as f:
            json.dump(hechos, f, ensure_ascii=False, indent=2)
        logging.info("🧠 Hecho guardado correctamente.")
    except Exception as e:
        logging.warning(f"❌ Error guardando hecho: {e}")

def generate_elevenlabs_audio(text):
    try:
        text = text[:800]
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"}
        data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.ok and response.content:
            path = f"/tmp/{uuid.uuid4()}.mp3"
            with open(path, "wb") as f:
                f.write(response.content)
            logging.info("✅ Audio generado exitosamente.")
            return path
    except Exception as e:
        logging.exception("❌ Excepción al generar audio")
    return None

def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        return transcript.text

def handle_text(update, context):
    text = update.message.text
    if text.lower().startswith("recordar "):
        hecho = text[9:].strip()
        guardar_hecho(hecho)
        update.message.reply_text("Hecho guardado.")
        return
    reply = get_openai_response(text)
    audio = generate_elevenlabs_audio(reply)
    if audio:
        context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
    else:
        update.message.reply_text(reply)

def handle_voice(update, context):
    file = context.bot.get_file(update.message.voice.file_id)
    ogg_path = f"/tmp/{uuid.uuid4()}.ogg"
    mp3_path = ogg_path.replace(".ogg", ".mp3")
    file.download(ogg_path)
    try:
        AudioSegment.from_ogg(ogg_path).export(mp3_path, format="mp3")
        transcript = transcribe_audio(mp3_path)
        reply = get_openai_response(transcript)
        audio = generate_elevenlabs_audio(reply)
        if audio:
            context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(audio, 'rb'))
        else:
            update.message.reply_text(reply)
    except Exception as e:
        logging.exception("❌ Error procesando audio")
        update.message.reply_text("Hubo un problema procesando tu audio.")

dispatcher.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 ¡Hola! Soy Carobot.")))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice))

@app.route("/", methods=["GET"])
def index():
    return "Carobot online", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
    logging.info(f"🔧 Webhook manual: {res.status_code} {res.text}")
    return {"status": res.status_code, "response": res.json()}

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        logging.exception("❌ Error procesando webhook")
    return "ok", 200

if os.environ.get("RAILWAY_ENVIRONMENT") == "production":
    try:
        url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
        res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
        logging.info(f"🔧 Webhook auto-seteado: {res.status_code} {res.text}")
    except Exception as e:
        logging.exception("❌ Error seteando webhook automáticamente")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    logging.info(f"🚀 Lanzando localmente en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
