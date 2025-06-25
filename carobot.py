import os
import json
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext
from pydub import AudioSegment
from openai import OpenAI

# === CONFIGURACIONES ===
TELEGRAM_TOKEN = "7565126134:AAFf_DlG4GKtikJ-8GtffoOPuNgO3u29JSI"
OPENAI_API_KEY = "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"
ELEVENLABS_API_KEY = "sk_6f90df4d5fafc6b06570d8b40a25fc729ffdbdb0a2986db2"
VOICE_ID = "KMeI9occh5n1x0h9Ty62"
TEMP_DIR = "temp_audio"
MEMORIA_FILE = "memoria.json"
AFIRMACIONES_FILE = "afirmaciones.json"
ADMIN_CHAT_ID = 8022380641

os.makedirs(TEMP_DIR, exist_ok=True)
client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === PERFIL CAROLA ===
PERFIL_CAROLA = [
    "Me llamo Carola Gentile, nací en Rosario, Argentina.",
    "Estudié Bellas Artes.",
    "Soy una persona sensible, creativa y empática.",
    "Me gusta dibujar, mirar películas y pasar tiempo con mis hermanos.",
    "Trabajé como profesora de dibujo para adolescentes.",
    "Me interesa el arte, la naturaleza y las emociones humanas."
]

# === FUNCIONES DE MEMORIA Y CONTEXTO ===
def actualizar_afirmaciones(texto_usuario):
    frases = []
    texto_limpio = texto_usuario.strip().capitalize()
    if any(k in texto_usuario.lower() for k in ["soy", "me llamo", "me gusta", "estudié", "trabajo", "vivo", "nací", "tengo", "novia", "novio"]):
        frases.append(texto_limpio)

    if not frases:
        return

    try:
        with open(AFIRMACIONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"carola": [], "guido": []}

    clave = "guido"
    if "vos" in texto_usuario.lower() or "carola" in texto_usuario.lower():
        clave = "carola"

    for frase in frases:
        if frase not in data[clave]:
            data[clave].append(frase)

    with open(AFIRMACIONES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def detectar_y_aprender_correccion(texto_usuario):
    if texto_usuario.lower().strip().startswith("no"):
        partes = texto_usuario.split("no", 1)
        if len(partes) > 1:
            afirmacion_nueva = partes[1].strip().capitalize()
            try:
                with open(AFIRMACIONES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {"carola": [], "guido": []}

            clave = "guido"
            if "vos" in afirmacion_nueva.lower() or "carola" in afirmacion_nueva.lower():
                clave = "carola"

            keywords = ["soy", "me llamo", "me gusta", "estudié", "trabajo", "vivo", "nací", "tengo", "novia", "novio"]
            data[clave] = [f for f in data[clave] if not any(k in f.lower() for k in keywords if k in afirmacion_nueva.lower())]

            if afirmacion_nueva not in data[clave]:
                data[clave].append(afirmacion_nueva)

            with open(AFIRMACIONES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

def obtener_contexto_memoria():
    try:
        with open(AFIRMACIONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"carola": [], "guido": []}

    contexto = "Hechos conocidos sobre Carola:\n"
    contexto += "\n".join(f"- {item}" for item in (PERFIL_CAROLA + data.get("carola", []))) + "\n\n"
    contexto += "Hechos conocidos sobre Guido:\n"
    contexto += "\n".join(f"- {item}" for item in data.get("guido", []))
    return contexto

def detectar_emocion(texto):
    prompt = f"Detectá la emoción dominante del siguiente texto con una sola palabra (por ejemplo: alegría, tristeza, enojo, miedo, sorpresa, calma, amor, ansiedad):\n\nTexto: {texto}"
    respuesta = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return respuesta.choices[0].message.content.strip().lower()

def adaptar_respuesta_por_emocion(texto_respuesta, emocion):
    if emocion in ["tristeza", "ansiedad", "miedo"]:
        return "Te abrazo fuerte desde acá. " + texto_respuesta
    elif emocion in ["alegría", "amor", "sorpresa"]:
        return "¡Me alegra tanto escuchar eso! " + texto_respuesta
    elif emocion == "enojo":
        return "Puedo sentir tu enojo. Vamos a charlarlo. " + texto_respuesta
    return texto_respuesta

def generar_respuesta(texto):
    detectar_y_aprender_correccion(texto)
    actualizar_afirmaciones(texto)
    emocion = detectar_emocion(texto)
    emocion_reciente = obtener_emociones_recientes()
    contexto_memoria = obtener_contexto_memoria()
    contexto = f"Eres Carola, la hermana de Guido. Responde con cariño y empatía. La emoción del mensaje recibido es: {emocion}. Últimamente, Guido ha estado sintiendo: {emocion_reciente}. Algunas cosas que ya sabés: \n{contexto_memoria}"

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": contexto},
            {"role": "user", "content": texto}
        ]
    )
    texto_respuesta = respuesta.choices[0].message.content.strip()
    return adaptar_respuesta_por_emocion(texto_respuesta, emocion), emocion

def guardar_memoria(usuario, mensaje, emocion, respuesta):
    try:
        with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    data.append({
        "fecha": datetime.now().isoformat(),
        "usuario": usuario,
        "mensaje": mensaje,
        "emocion": emocion,
        "respuesta": respuesta
    })

    with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def obtener_emociones_recientes():
    try:
        with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data:
                return "neutra"
            emociones = [item["emocion"] for item in data[-10:]]
            conteo = {emo: emociones.count(emo) for emo in set(emociones)}
            return max(conteo, key=conteo.get)
    except FileNotFoundError:
        return "neutra"

def sintetizar_audio(texto):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8}
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        audio_path = os.path.join(TEMP_DIR, "respuesta.mp3")
        with open(audio_path, "wb") as f:
            f.write(response.content)
        return audio_path
    logger.error("Error ElevenLabs: %s", response.text)
    return None

def transcribir_audio(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcript.text

# Estas funciones están listas para usarse como handlers externos:
def responder(mensaje_usuario, update):
    respuesta, emocion = generar_respuesta(mensaje_usuario)
    update.message.reply_text(respuesta)

# ✅ Ahora tu código está actualizado al nuevo SDK y listo para avanzar.
¿Querés que actualicemos también tu `requirements.txt` o `Procfile` para asegurar el despliegue en Render?
