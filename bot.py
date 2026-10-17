import os
import sqlite3
import logging
from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# NOTUN BOT TOKEN & ADMIN ID
TOKEN = "8624066909:AAEzSG-mMxGGZgXlffeMaJG-4NFNsoia0hI"
ADMIN_ID = 6132325140  

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT,
            item_data TEXT,
            price REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, username):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, 0.0))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    conn.close()
    return balance

def update_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- ADMIN COMMANDS ---
async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return

    try:
        args = context.args
        item_type = args[0].lower()
        price = float(args[1])
        item_data = " ".join(args[2:])

        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO stock (item_type, item_data, price) VALUES (?, ?, ?)", (item_type, item_data, price))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ Added {item_type}!\nPrice: ${price}\nData: `{item_data}`", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ Format: `/add number 1.5 +8801700000000`", parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return

    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Shudhu .txt file upload karun!")
        return

    caption = update.message.caption
    if not caption or not caption.startswith("/addfile"):
        await update.message.reply_text("⚠️ Caption format: `/addfile number 1.5`", parse_mode="Markdown")
        return

    try:
        args = caption.split()
        item_type = args[1].lower()
        price = float(args[2])

        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        content = file_bytes.decode('utf-8')

        lines = [line.strip() for line in content.splitlines() if line.strip()]

        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        stock_data = [(item_type, line, price) for line in lines]
        cursor.executemany("INSERT INTO stock (item_type, item_data, price) VALUES (?, ?, ?)", stock_data)
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🎉 Bulk Import Success!\n📦 Type: `{item_type}`\n🔢 Total Added: `{len(lines)}`", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def add_bal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        update_balance(target_user_id, amount)
        await update.message.reply_text(f"✅ Added ${amount} to User ID: `{target_user_id}`", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ Format: `/addbal USER_ID AMOUNT`", parse_mode="Markdown")

# --- USER COMMANDS & MENUS ---
async def post_init(application):
    commands = [BotCommand("start", "🔄 Restart Bot / Show Menu")]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username)

    welcome_text = f"👋 **Welcome, {user.first_name}!**\n\nMarketplace bot-e apnake shagotom."
    keyboard = [
        ["🛒 Buy number", "📧 Buy email"],
        ["💰 Deposit", "👤 Profile"],
        ["💸 Withdraw"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    if text == "👤 Profile":
        balance = get_user(user.id, user.username)
        profile_text = f"👤 **Profile:**\n🆔 ID: `{user.id}`\n💰 Balance: `${balance:.2f} USDT`"
        await update.message.reply_text(profile_text, parse_mode="Markdown")

    elif text == "💰 Deposit":
        keyboard = [
            [InlineKeyboardButton("bKash / Nagad", callback_data="pay_bkash")],
            [InlineKeyboardButton("Crypto (USDT/TRC20)", callback_data="pay_crypto")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💳 Deposit method select karun:", reply_markup=reply_markup)

    elif text in ["🛒 Buy number", "📧 Buy email"]:
        item_type = "number" if text == "🛒 Buy number" else "email"
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_data, price FROM stock WHERE item_type = ? LIMIT 1", (item_type,))
        stock_item = cursor.fetchone()

        if not stock_item:
            await update.message.reply_text(f"❌ Current {item_type} stock is empty!")
            conn.close()
            return

        stock_id, item_data, price = stock_item
        user_balance = get_user(user.id, user.username)

        if user_balance < price:
            await update.message.reply_text(f"⚠️ Insufficient balance! Price: ${price}, Balance:${user_balance:.2f}")
            conn.close()
            return

        update_balance(user.id, -price)
        cursor.execute("DELETE FROM stock WHERE id = ?", (stock_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🎉 **Purchase Successful!**\n📦 Type: {item_type}\n🔑 Details: `{item_data}`", parse_mode="Markdown")

    elif text == "💸 Withdraw":
        await update.message.reply_text("💸 Balance porjapto noi.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "pay_bkash":
        await query.edit_message_text(f"📲 Send Money to `017XXXXXXXX` and notify Admin with User ID (`{query.from_user.id}`).")
    elif query.data == "pay_crypto":
        await query.edit_message_text(f"🪙 Send USDT to `TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` and notify Admin with User ID (`{query.from_user.id}`).")

def main():
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_stock))
    application.add_handler(CommandHandler("addbal", add_bal))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("New Bot is running cleanly...")
    application.run_polling()

if __name__ == "__main__":
    main()