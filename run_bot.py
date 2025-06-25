import os
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from carobot import responder

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN no fue encontrado. Verificá el archivo .env o las variables en Render.")

print(f"✅ TELEGRAM_TOKEN recibido: {repr(TOKEN)}")

# Handlers
def start(update, context):
    update.message.reply_text("¡Carobot está activo y en modo polling!")

def handle(update, context):
    try:
        texto = update.message.text
        print(f"📩 Mensaje recibido: {texto}")
        responder(texto, update)
    except Exception as e:
        print("❌ Error en handler de mensaje:", e)
        update.message.reply_text("Ups, hubo un problema al procesar tu mensaje.")

# Iniciar el bot
if __name__ == '__main__':
    print("🚀 Iniciando Carobot...")
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))

    updater.start_polling()
    updater.idle()
