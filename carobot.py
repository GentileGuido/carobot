import os
import logging
import tempfile
import requests
from openai import OpenAI
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext
from pydub import AudioSegment

# --- Cargar variables de entorno ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")  # opcional, puede ser una voz personalizada

# --- Inicializar cliente OpenAI ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Inicializar logs ---
logging.basicConfig(level=logging.INFO)

def responder(mensaje: str, update: Update, context: CallbackContext = None):
    try:
        # --- Obtener respuesta de OpenAI ---
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Sos Carobot, hablás como Carola y usás un tono cálido y cercano."},
                {"role": "user", "content": mensaje}
            ],
            temperature=0.7
        )
        respuesta_texto = response.choices[0].message.content.strip()

        # --- Llamar a ElevenLabs para generar la voz ---
        audio = sintetizar_audio_eleventy(respuesta_texto)

        # --- Enviar audio por Telegram ---
        if audio:
            update.message.reply_voice(voice=audio)
        else:
            update.message.reply_text(respuesta_texto)

    except Exception as e:
        logging.exception("Error en manejar_mensaje:")
        update.message.reply_text("Ups, algo falló...")

def sintetizar_audio_eleventy(texto):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID or 'Rachel'}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8
            }
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logging.error(f"Error en ElevenLabs: {response.status_code}, {response.text}")
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(response.content)
            temp_file.flush()

            # Convertir MP3 a OGG (Telegram solo acepta .ogg/.opus para notas de voz)
            ogg_path = temp_file.name.replace(".mp3", ".ogg")
            sound = AudioSegment.from_mp3(temp_file.name)
            sound.export(ogg_path, format="ogg", codec="libopus")
            return open(ogg_path, "rb")

    except Exception as e:
        logging.exception("Error al generar audio con ElevenLabs")
        return None
