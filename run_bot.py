from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from carobot import responder
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

def start(update, context):
    update.message.reply_text("¡Carobot en modo polling!")

def handle(update, context):
    responder(update.message.text, update)

updater = Updater(token=TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
updater.start_polling()
updater.idle()
