import os
import sqlite3
import logging
from threading import Thread
from flask import Flask
from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Render Free Web Service Dummy Server Setup
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# BOT TOKEN & ADMIN ID
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

def get_stock_info(item_type):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), price FROM stock WHERE item_type = ?", (item_type,))
    row = cursor.fetchone()
    conn.close()
    count = row[0] if row else 0
    price = row[1] if row and row[1] is not None else 0.0
    return count, price

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
        await update.message.reply_text("❌ Format: `/add whatsapp 0.09 +8801700000000`", parse_mode="Markdown")

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
        await update.message.reply_text("⚠️ Caption format: `/addfile whatsapp 0.09` or `/addfile telegram 0.15`", parse_mode="Markdown")
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

        await update.message.reply_text(f"🎉 Bulk Import Success!\n📦 Category: `{item_type}`\n🔢 Total Added: `{len(lines)}`", parse_mode="Markdown")

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

# --- USER MENUS ---
def get_main_keyboard():
    keyboard = [
        ["🛒 Buy Number"],
        ["💰 Deposit", "👤 Profile"],
        ["💸 Withdraw"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_platform_keyboard():
    keyboard = [
        ["📱 WhatsApp", "✈️ Telegram"],
        ["🔙 Back"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_purchase_type_keyboard():
    keyboard = [
        ["1️⃣ Single Purchase", "📦 Bulk purchase"],
        ["🔙 Back"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def post_init(application):
    commands = [BotCommand("start", "🔄 Restart Bot / Show Menu")]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username)
    context.user_data.clear()

    welcome_text = f"👋 **Welcome, {user.first_name}!**\n\nChoose an option below:"
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def show_buy_menu(update: Update):
    wa_count, wa_price = get_stock_info("whatsapp")
    tg_count, tg_price = get_stock_info("telegram")

    msg_text = (
        "🛒 **Buy Number**\n"
        "━━━━━━━\n"
        "Select the platform you need 👇\n\n"
        f"📱 **WhatsApp** — 📦 `{wa_count}` in stock • 💰 `{wa_price:.2f}` USDT\n"
        f"✈️ **Telegram** — 📦 `{tg_count}` in stock • 💰 `{tg_price:.2f}` USDT"
    )
    await update.message.reply_text(msg_text, reply_markup=get_platform_keyboard(), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    if text == "🛒 Buy Number":
        context.user_data["step"] = "category"
        await show_buy_menu(update)

    elif text in ["📱 WhatsApp", "✈️ Telegram"]:
        platform = "whatsapp" if "WhatsApp" in text else "telegram"
        platform_title = "WhatsApp Numbers" if platform == "whatsapp" else "Telegram Numbers"
        
        context.user_data["selected_platform"] = platform
        context.user_data["step"] = "purchase_type"

        count, price = get_stock_info(platform)

        msg_text = (
            f"📱 **{platform_title}**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🇺🇸 USA +1 {platform.title()} Number Only\n\n"
            f"📦 **Stock:** {count} numbers\n"
            f"💰 **Price:** {price:.2f} USDT per number ⭐ *your special rate*\n\n"
            "নাম্বারে ওটিপি না আসলে রিফান্ড পাবেন। বিস্তারিত না পড়ে নাম্বার কিনবেন না।\n"
            "Choose an option:"
        )
        await update.message.reply_text(msg_text, reply_markup=get_purchase_type_keyboard(), parse_mode="Markdown")

    elif text == "1️⃣ Single Purchase":
        platform = context.user_data.get("selected_platform", "whatsapp")
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_data, price FROM stock WHERE item_type = ? LIMIT 1", (platform,))
        stock_item = cursor.fetchone()

        if not stock_item:
            await update.message.reply_text(f"❌ Current {platform.upper()} stock is empty!", reply_markup=get_purchase_type_keyboard())
            conn.close()
            return

        stock_id, item_data, price = stock_item
        user_balance = get_user(user.id, user.username)

        if user_balance < price:
            await update.message.reply_text(f"⚠️ Insufficient balance! Price: ${price:.2f}, Balance:${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
            conn.close()
            return

        update_balance(user.id, -price)
        cursor.execute("DELETE FROM stock WHERE id = ?", (stock_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🎉 **Single Purchase Successful!**\n📦 Platform: `{platform.upper()}`\n🔑 Details: `{item_data}`", reply_markup=get_purchase_type_keyboard(), parse_mode="Markdown")

    elif text == "📦 Bulk purchase":
        platform = context.user_data.get("selected_platform", "whatsapp")
        count = 5  # Standard bulk limit

        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_data, price FROM stock WHERE item_type = ? LIMIT ?", (platform, count))
        items = cursor.fetchall()

        if len(items) < count:
            await update.message.reply_text(f"❌ Not enough stock! Available: {len(items)}, Required: {count}", reply_markup=get_purchase_type_keyboard())
            conn.close()
            return

        total_price = sum(item[2] for item in items)
        user_balance = get_user(user.id, user.username)

        if user_balance < total_price:
            await update.message.reply_text(f"⚠️ Insufficient balance! Total Cost: ${total_price:.2f}, Balance:${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
            conn.close()
            return

        update_balance(user.id, -total_price)
        item_ids = [item[0] for item in items]
        item_details = "\n".join([f"- `{item[1]}`" for item in items])

        cursor.executemany("DELETE FROM stock WHERE id = ?", [(i,) for i in item_ids])
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🎉 **Bulk Purchase Successful!**\n📦 Platform: `{platform.upper()}`\n🔢 Items: {count}\n💰 Total Cost: `${total_price:.2f}`\n\n🔑 **Details:**\n{item_details}", reply_markup=get_purchase_type_keyboard(), parse_mode="Markdown")

    elif text == "🔙 Back":
        current_step = context.user_data.get("step")
        if current_step == "purchase_type":
            context.user_data["step"] = "category"
            await show_buy_menu(update)
        else:
            context.user_data.clear()
            await update.message.reply_text("🔙 Main menu-te phire asha hoyeche.", reply_markup=get_main_keyboard())

    elif text == "👤 Profile":
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

    elif text == "💸 Withdraw":
        await update.message.reply_text("💸 Balance porjapto noi.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "pay_bkash":
        await query.edit_message_text(f"📲 Send Money to `017XXXXXXXX` and notify Admin with User ID (`{user.id}`).", parse_mode="Markdown")
    elif data == "pay_crypto":
        await query.edit_message_text(f"🪙 Send USDT to `TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` and notify Admin with User ID (`{user.id}`).", parse_mode="Markdown")

def main():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_stock))
    application.add_handler(CommandHandler("addbal", add_bal))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot updated matching screenshot keyboard layout...")
    application.run_polling()

if __name__ == "__main__":
    main()