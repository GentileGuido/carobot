import os
import openai
import requests
from pydub import AudioSegment
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

# --- Claves de API ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID")  # por ejemplo: "EXAVITQu4vr4xnSDxMaL"

openai.api_key = OPENAI_API_KEY

# --- Transcribir audio (Telegram -> MP3 -> Texto) ---
def transcribir_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        print("Error al transcribir audio:", e)
        return "Lo siento, no pude entender el audio."

# --- Generar respuesta con GPT-4 ---
def generar_respuesta(texto):
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": texto}],
            temperature=0.7
        )
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        print("Error al generar respuesta:", e)
        return "Tuve un problema al pensar mi respuesta."

# --- Convertir texto a voz con ElevenLabs ---
def texto_a_voz(texto, filename="respuesta.mp3"):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": texto,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return filename
        else:
            print("Error ElevenLabs:", response.text)
            return None
    except Exception as e:
        print("Error en ElevenLabs:", e)
        return None

# --- Función principal para manejar texto o audio ---
def responder(mensaje, update):
    chat_id = update.message.chat_id

    # Si es un audio
    if update.message.voice:
        try:
            # 1. Descargar el archivo de voz
            voice_file = update.message.voice.get_file()
            ogg_path = f"audio_{chat_id}.ogg"
            mp3_path = f"audio_{chat_id}.mp3"
            voice_file.download(ogg_path)

            # 2. Convertir a mp3
            AudioSegment.from_ogg(ogg_path).export(mp3_path, format="mp3")

            # 3. Transcribir
            texto_transcrito = transcribir_audio(mp3_path)
            update.message.reply_text(f"📜 {texto_transcrito}")

            # 4. Generar respuesta
            respuesta = generar_respuesta(texto_transcrito)

            # 5. Responder en voz
            archivo_voz = texto_a_voz(respuesta)
            if archivo_voz:
                update.message.reply_voice(voice=open(archivo_voz, "rb"))
            else:
                update.message.reply_text(respuesta)

        except Exception as e:
            print("Error en manejo de audio:", e)
            update.message.reply_text("Hubo un problema con el audio. Intentá de nuevo.")
    
    # Si es un texto
    elif mensaje:
        respuesta = generar_respuesta(mensaje)
        archivo_voz = texto_a_voz(respuesta)
        if archivo_voz:
            update.message.reply_voice(voice=open(archivo_voz, "rb"))
        else:
            update.message.reply_text(respuesta)

def main():
    print("✅ Carobot se inició correctamente (modo manual/test). Esperando mensajes desde main.py...")

if __name__ == '__main__':
    main()

