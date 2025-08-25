import os
import requests
from openai import OpenAI
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID", "EXAMPLE_ID")

results = {}

# Test Telegram
try:
    bot = Bot(token=TELEGRAM_TOKEN)
    me = bot.get_me()
    results["telegram"] = f"✅ OK - Bot: {me.first_name}"
except Exception as e:
    results["telegram"] = f"❌ Error: {e}"

# Test OpenAI Chat y Transcripción
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    preferred_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    chat = client.chat.completions.create(
        model=preferred_model,
        messages=[{"role": "user", "content": "Hola"}],
        max_tokens=5
    )
    results["openai_chat"] = f"✅ OK - {preferred_model}"
except Exception as e:
    results["openai_chat"] = f"❌ {type(e).__name__}: {e}"

try:
    # Crea un wav vacío de 0.5s para probar credenciales del endpoint
    import io, wave
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00" * 16000)
    buf.seek(0)
    tr = client.audio.transcriptions.create(model="whisper-1", file=buf)
    results["openai_transcribe"] = "✅ OK whisper-1"
except Exception as e:
    results["openai_transcribe"] = f"❌ {type(e).__name__}: {e}"

# Test ElevenLabs
try:
    url = f"https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": ELEVEN_API_KEY}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        results["elevenlabs"] = "✅ OK"
    else:
        results["elevenlabs"] = f"❌ Error {res.status_code}: {res.text}"
except Exception as e:
    results["elevenlabs"] = f"❌ Error: {e}"

print("\n🔎 Resultados del test de claves:\n")
for service, result in results.items():
    print(f"{service}: {result}")
