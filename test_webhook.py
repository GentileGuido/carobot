import os
import requests

# Asegúrate de tener seteada esta variable o ponela directamente aquí
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
res = requests.get(url)

if res.status_code == 200:
    data = res.json()
    print("✅ Webhook Info:")
    print(data["result"])
else:
    print("❌ Error al consultar el webhook:")
    print(res.status_code, res.text)
