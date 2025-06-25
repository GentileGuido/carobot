import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("7565126134:AAF0ZO6r4DxCwLNmZLiMw3xDg8GtUMgy4e4")
URL = "https://carobot.onrender.com"

if not TOKEN:
    raise ValueError("No se encontró TELEGRAM_TOKEN en .env")

response = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={URL}/{TOKEN}"
)

print("Webhook:", response.status_code)
print(response.json())
