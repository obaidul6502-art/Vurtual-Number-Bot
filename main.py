import os
import logging
from threading import Thread
from flask import Flask
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import TOKEN
from database import init_db
from handlers.admin import (
    add_stock, 
    handle_document, 
    add_bal, 
    admin_users_command, 
    maintenance_command, 
    broadcast_command
)
from handlers.user import start, handle_message, button_callback

# Flask app for Render liveness ping
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Logging configuration
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def post_init(application):
    commands = [
        BotCommand("start", "🔄 Restart Bot / Show Menu"),
        BotCommand("users", "👥 View All Users & Balances (Admin)")
    ]
    await application.bot.set_my_commands(commands)

def main():
    # Initialize Database tables
    init_db()

    # Start Flask server in a separate background thread
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    # Build Telegram Application
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", admin_users_command))
    application.add_handler(CommandHandler("add", add_stock))
    application.add_handler(CommandHandler("addbal", add_bal))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Modular Bot started successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()