import os
import requests
from dotenv import load_dotenv

# Carga las claves del .env
load_dotenv()
API_KEY = os.getenv("ELEVENLABS_API_KEY")

def test_elevenlabs_key():
    if not API_KEY:
        print("❌ ELEVENLABS_API_KEY no cargada.")
        return

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "xi-api-key": API_KEY
    }

    print("🔍 Testeando API Key de ElevenLabs...")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("✅ API Key válida. Respuesta correcta.")
    else:
        print(f"❌ Error al validar key. Código {response.status_code}")
        print("Detalles:", response.text)

if __name__ == "__main__":
    test_elevenlabs_key()
