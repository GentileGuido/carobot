# set_webhook.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL") or "https://carobot.onrender.com"

if not TOKEN:
    raise ValueError("No se encontró TELEGRAM_TOKEN en .env")

webhook_url = f"{URL}/webhook"
response = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
)

print("Webhook:", response.status_code)
print(response.json())
