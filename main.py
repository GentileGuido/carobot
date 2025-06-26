from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from queue import Queue
import os
import requests
from pydub import AudioSegment
from openai import OpenAI

# 👉 Agregá esta línea:
print("🔑 OPENAI_API_KEY desde entorno (inicio):", repr(OPENAI_API_KEY[:20] + "..."))

# 🔐 Cargar variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVEN_VOICE_ID = os.getenv("VOICE_ID")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"
WEBHOOK_PATH = "/webhook"

# 🧪 Verificar que se cargaron las claves
print("🔑 OPENAI_API_KEY desde entorno:", repr(OPENAI_API_KEY))

def test_keys():
    results = {}

    try:
        bot_test = Bot(token=TELEGRAM_TOKEN)
        bot_test.get_me()
        results["telegram"] = "✅ OK"
    except Exception as e:
        results["telegram"] = f"❌ Telegram: {e}"

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        client.models.list()
        results["openai"] = "✅ OK"
    except Exception as e:
        results["openai"] = f"❌ OpenAI: {e}"

    try:
        headers = {"xi-api-key": ELEVEN_API_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        if r.status_code == 200:
            results["elevenlabs"] = "✅ OK"
        else:
            results["elevenlabs"] = f"❌ ElevenLabs: {r.status_code} - {r.text}"
    except Exception as e:
        results["elevenlabs"] = f"❌ ElevenLabs: {e}"

    return results

print(test_keys())

# 🚨 Validaciones mínimas antes de iniciar
if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Falta TELEGRAM_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ Falta OPENAI_API_KEY")

# ✅ Inicializar Flask
app = Flask(__name__)
print("✅ Flask inicializado")

# 🤖 Inicializar bot y cliente OpenAI
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, update_queue=Queue(), workers=1, use_context=True)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 🔊 Funciones de IA
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
        return f"Tuve un problema generando mi respuesta. Error: {str(e)}"

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

# 🧠 Manejo de mensajes entrantes
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
            respuesta = generar_respuesta(transcripcion)

        voz = texto_a_voz(respuesta)
        if voz:
            msg.reply_voice(voice=open(voz, "rb"))
        else:
            msg.reply_text(respuesta)

    except Exception as e:
        print("❌ Error general:", e)
        msg.reply_text(f"Tuve un problema procesando el mensaje. Error: {str(e)}")

# 📥 Handlers
dispatcher.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 ¡Hola! Soy Carobot.")))
dispatcher.add_handler(MessageHandler(Filters.voice, responder))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, responder))

# 🌐 Rutas Flask
@app.route("/", methods=["GET"])
def index():
    print("🌐 GET /")
    return "✅ Carobot Webhook listo", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    print("⚙️ Intentando setear webhook...")
    url = f"{RENDER_URL}{WEBHOOK_PATH}"
    res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}")
    print("🔁 Webhook response:", res.status_code, res.json())
    return {"status": res.status_code, "response": res.json()}, res.status_code

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    print("📡 Webhook recibido")
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        print("❌ Error en webhook:", e)
    return "ok", 200

# ▶️ Ejecutar app
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    print(f"🚀 Carobot lanzado en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
