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

# Test OpenAI
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    chat = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hola"}],
        max_tokens=5
    )
    results["openai"] = "✅ OK"
except Exception as e:
    results["openai"] = f"❌ OpenAI: {e}"

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
