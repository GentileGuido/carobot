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
import re

# 🔐 Variables de entorno
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
    ELEVEN_VOICE_ID = os.environ["VOICE_ID"]
    PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "https://carobot-production.up.railway.app")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4")  # Parametrizable; rollback fácil cambiando la env var
    OPENAI_FALLBACK_MODEL = os.environ.get("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")
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
ESTADO_PATH = "estado.json"
PERFIL_PATH = "perfil_carola.txt"
try:
    FOLLOWUP_HOURS = float(os.environ.get("FOLLOWUP_HOURS", "24"))
except Exception:
    FOLLOWUP_HOURS = 24.0

SYSTEM_PROMPT = (
    "Sos Carobot, una inteligencia emocional y sensible. Respondés en un tono humano y cercano, "
    "pero de forma breve y clara. No repetís frases hechas ni te extendés innecesariamente. "
    "Seguís el hilo de lo que te cuentan y, si corresponde, preguntás con suavidad cómo siguió."
)

def _cargar_perfil_texto():
    try:
        if os.path.exists(PERFIL_PATH):
            with open(PERFIL_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        logging.warning(f"⚠️ No se pudo leer perfil en {PERFIL_PATH}: {e}")
    return ""

PERFIL_TEXTO = _cargar_perfil_texto()

def _leer_json_lista_seguro(path):
    """Lee un JSON y garantiza lista; si está corrupto devuelve lista vacía y loguea warning."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except json.JSONDecodeError:
        logging.warning(f"⚠️ JSON inválido en {path}. Reiniciando a lista vacía.")
    except Exception as e:
        logging.warning(f"⚠️ Error leyendo {path}: {e}")
    return []


def _leer_json_dict_seguro(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except json.JSONDecodeError:
        logging.warning(f"⚠️ JSON inválido en {path}. Reiniciando a dict vacío.")
    except Exception as e:
        logging.warning(f"⚠️ Error leyendo {path}: {e}")
    return {}


def detectar_mood(texto):
    if not texto:
        return None
    t = texto.lower()
    # Heurística simple en español
    patrones = [
        (r"\b(me\s+siento|estoy|and(o|a)\s+)(muy\s+)?(bien|feliz|content[oa]|tranquil[oa])\b", "bien"),
        (r"\b(me\s+siento|estoy|and(o|a)\s+)(muy\s+)?(mal|triste|angustiad[oa]|ansios[oa]|enojad[oa]|deprimid[oa]|cansad[oa])\b", "mal"),
    ]
    for patron, etiqueta in patrones:
        if re.search(patron, t):
            return etiqueta
    # Palabras sueltas
    if re.search(r"\b(feliz|content[oa]|bien)\b", t):
        return "bien"
    if re.search(r"\b(mal|triste|angustiad[oa]|ansios[oa]|enojad[oa]|deprimid[oa]|cansad[oa])\b", t):
        return "mal"
    return None


def cargar_estado():
    return _leer_json_dict_seguro(ESTADO_PATH)


def actualizar_estado_emocional(texto):
    try:
        mood = detectar_mood(texto)
        if not mood:
            return
        estado = {
            "timestamp": datetime.datetime.now().isoformat(),
            "mood": mood,
            "resumen": texto[:140],
            # Al registrar un nuevo estado, reseteamos el flag de follow-up
            "followup_asked": False
        }
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        logging.info(f"🫀 Estado emocional actualizado: {mood}")
    except Exception as e:
        logging.warning(f"⚠️ No se pudo actualizar estado emocional: {e}")


def marcar_followup_preguntado():
    try:
        estado = cargar_estado()
        if not estado:
            return
        estado["followup_asked"] = True
        estado["followup_asked_at"] = datetime.datetime.now().isoformat()
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"⚠️ No se pudo marcar follow-up como preguntado: {e}")


def guardar_en_memoria(entrada, respuesta):
    try:
        memoria = _leer_json_lista_seguro(MEMORIA_PATH)

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
        logging.info("📤 Enviando a OpenAI")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Identidad base de Carobot (Carola)
        if PERFIL_TEXTO:
            messages.append({"role": "system", "content": f"Identidad base: {PERFIL_TEXTO}"})

        hechos = _leer_json_lista_seguro(HECHOS_PATH)
        for h in hechos[-20:]:
            try:
                messages.append({"role": "system", "content": f"Recordá esto: {h['hecho']}"})
            except Exception:
                continue

        memoria = _leer_json_lista_seguro(MEMORIA_PATH)
        for item in memoria[-1000:]:
            try:
                messages.append({"role": "user", "content": item["entrada"]})
                messages.append({"role": "assistant", "content": item["respuesta"]})
            except Exception:
                continue

        # Seguimiento emocional: si la persona reportó ánimo antes y hoy no lo menciona, sugerir un check-in
        estado = cargar_estado()
        mood_en_prompt = detectar_mood(prompt)
        followup_debido = False
        if estado and not mood_en_prompt and not estado.get("followup_asked", False):
            try:
                ts = datetime.datetime.fromisoformat(estado.get("timestamp"))
                horas = (datetime.datetime.now() - ts).total_seconds() / 3600.0
                if horas >= FOLLOWUP_HOURS:
                    breve_fecha = ts.strftime("%d/%m %H:%M")
                    messages.append({
                        "role": "system",
                        "content": (
                            f"Seguimiento emocional pendiente: la última vez el usuario dijo sentirse '{estado.get('mood')}' el {breve_fecha}. "
                            "Si no lo menciona, preguntá con suavidad si siguió igual o cambió."
                        )
                    })
                    followup_debido = True
            except Exception:
                pass

        messages.append({"role": "user", "content": prompt})
        # Modelo parametrizable por env var; fallback automático si falla
        try:
            res = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
        except Exception as primary_err:
            logging.warning(f"⚠️ Modelo primario '{OPENAI_MODEL}' falló. Probando fallback '{OPENAI_FALLBACK_MODEL}'.")
            res = client.chat.completions.create(model=OPENAI_FALLBACK_MODEL, messages=messages)
        content = res.choices[0].message.content
        guardar_en_memoria(prompt, content)
        if 'followup_debido' in locals() and followup_debido:
            marcar_followup_preguntado()
        return content
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg or "invalid_api_key" in msg:
            logging.error("❌ Error OpenAI 401/Unauthorized. Revisar OPENAI_API_KEY (no se imprime por seguridad).")
        elif "403" in msg or "insufficient_quota" in msg:
            logging.error("❌ Error OpenAI 403/Quota. Créditos agotados o sin permisos.")
        else:
            logging.error(f"❌ Error con OpenAI: {e}")
        return "No pude procesar tu mensaje."

def guardar_hecho(texto):
    try:
        hechos = _leer_json_lista_seguro(HECHOS_PATH)
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
        if response.status_code == 401 and "quota_exceeded" in response.text:
            logging.warning("🔇 ElevenLabs sin créditos (401 quota_exceeded). Enviando solo texto.")
            return None
        if response.ok and response.content:
            path = f"/tmp/{uuid.uuid4()}.mp3"
            with open(path, "wb") as f:
                f.write(response.content)
            logging.info("✅ Audio generado exitosamente.")
            return path
        # Otros errores HTTP
        logging.error(f"❌ ElevenLabs error HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logging.exception("❌ Excepción al generar audio")
    return None

def transcribe_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            return transcript.text
    except Exception as e:
        logging.error(f"❌ Error transcribiendo audio: {e}")
        return None

def handle_text(update, context):
    text = update.message.text
    if text.lower().startswith("recordar "):
        hecho = text[9:].strip()
        guardar_hecho(hecho)
        update.message.reply_text("Hecho guardado.")
        return
    reply = get_openai_response(text)
    audio_path = generate_elevenlabs_audio(reply)
    if audio_path:
        try:
            with open(audio_path, 'rb') as vf:
                context.bot.send_voice(chat_id=update.effective_chat.id, voice=vf)
        finally:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass
    else:
        update.message.reply_text(reply)
    # Actualizamos estado emocional en base al nuevo texto
    actualizar_estado_emocional(text)

def handle_voice(update, context):
    file = context.bot.get_file(update.message.voice.file_id)
    ogg_path = f"/tmp/{uuid.uuid4()}.ogg"
    mp3_path = ogg_path.replace(".ogg", ".mp3")
    file.download(ogg_path)
    try:
        AudioSegment.from_ogg(ogg_path).export(mp3_path, format="mp3")
        transcript = transcribe_audio(mp3_path)
        if not transcript:
            update.message.reply_text("No pude transcribir tu nota de voz.")
            return
        reply = get_openai_response(transcript)
        audio_path = generate_elevenlabs_audio(reply)
        if audio_path:
            try:
                with open(audio_path, 'rb') as vf:
                    context.bot.send_voice(chat_id=update.effective_chat.id, voice=vf)
            finally:
                try:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                except Exception:
                    pass
        else:
            update.message.reply_text(reply)
    except Exception as e:
        logging.exception("❌ Error procesando audio")
        update.message.reply_text("Hubo un problema procesando tu audio.")
    finally:
        try:
            if os.path.exists(ogg_path):
                os.remove(ogg_path)
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
        except Exception:
            pass
    # Actualizamos estado emocional en base a la transcripción
    try:
        if 'transcript' in locals() and transcript:
            actualizar_estado_emocional(transcript)
    except Exception:
        pass

dispatcher.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 ¡Hola! Soy Carobot.")))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice))

@app.route("/", methods=["GET"])
def index():
    return "Carobot online", 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    res = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}", timeout=10
    )
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
        res = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}", timeout=10
        )
        logging.info(f"🔧 Webhook auto-seteado: {res.status_code} {res.text}")
    except Exception as e:
        logging.exception("❌ Error seteando webhook automáticamente")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    logging.info(f"🚀 Lanzando localmente en http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
