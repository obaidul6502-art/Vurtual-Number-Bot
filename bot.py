import os
import psycopg2
import logging
import re
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8624066909:AAEzSG-mMxGGZgXlffeMaJG-4NFNsoia0hI"
ADMIN_ID = 6132325140  
DATABASE_URL = os.environ.get("DATABASE_URL")

MAINTENANCE_MODE = False

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        raise Exception("DATABASE_URL environment variable is missing!")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id SERIAL PRIMARY KEY,
            item_type TEXT,
            item_data TEXT,
            price REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            platform TEXT,
            item_data TEXT,
            price REAL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()

def get_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (%s, %s, %s)", (user_id, username, 0.0))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    cursor.close()
    conn.close()
    return balance

def update_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return [u[0] for u in users]

def get_stock_info(item_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), AVG(price) FROM stock WHERE item_type = %s", (item_type,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    count = row[0] if row else 0
    price = row[1] if row and row[1] is not None else 0.0
    return count, price

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

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO stock (item_type, item_data, price) VALUES (%s, %s, %s)", (item_type, item_data, price))
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text(f"✅ Added {item_type}!\nPrice: ${price}\nData: {item_data}")

        users = get_all_users()
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🚨 New Stock Alert!\n\n📦 Platform: {item_type.upper()}\n💰 Price: ${price:.2f}\n\nEkhoni bot e giye number kinun!"
                )
            except Exception:
                pass
    except Exception:
        await update.message.reply_text("❌ Format: /add whatsapp 0.09 +8801700000000")

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
        await update.message.reply_text("⚠️ Caption format: /addfile whatsapp 0.09")
        return

    try:
        args = caption.split()
        item_type = args[1].lower()
        price = float(args[2])

        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        content = file_bytes.decode('utf-8')

        lines = [line.strip() for line in content.splitlines() if line.strip()]

        conn = get_db_connection()
        cursor = conn.cursor()
        for line in lines:
            cursor.execute("INSERT INTO stock (item_type, item_data, price) VALUES (%s, %s, %s)", (item_type, line, price))
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text(f"🎉 Bulk Import Success!\n📦 Category: {item_type}\n🔢 Total Added: {len(lines)}")

        users = get_all_users()
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🚀 New Stock Restocked!\n\n📦 Platform: {item_type.upper()}\n🔢 Added Quantity: {len(lines)} numbers\n💰 Price: ${price:.2f}\n\nStock sesh hobar age kine nin!"
                )
            except Exception:
                pass

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
        await update.message.reply_text(f"✅ Added ${amount} to User ID: {target_user_id}")
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 Deposit Successful!\n\nAdmin apnar account-e ${amount} add korechen. Ekhon apni number kinte paren!"
            )
        except Exception:
            await update.message.reply_text("⚠️ Balance added in DB, but couldn't send notification to user.")
    except Exception:
        await update.message.reply_text("❌ Format: /addbal USER_ID AMOUNT")

# --- ADMIN COMMAND TO SEE ALL USERS & BALANCES ---
async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        await update.message.reply_text("📁 Kono user nei database-e.")
        return

    msg = "👥 **All Registered Users & Balances:**\n━━━━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        uid, uname, bal = row
        msg += f"🆔 ID: `{uid}`\n👤 @{uname if uname else 'N/A'}\n💰 Balance: `${bal:.2f}`\n--------------------\n"
    
    if len(msg) > 4000:
        msg = msg[:4000] + "\n... (list too long)"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAINTENANCE_MODE
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    
    try:
        status = context.args[0].lower()
        if status == "on":
            MAINTENANCE_MODE = True
            await update.message.reply_text("⚠️ Bot is now in Maintenance Mode.")
        elif status == "off":
            MAINTENANCE_MODE = False
            await update.message.reply_text("✅ Bot is now Live / Active.")
        else:
            await update.message.reply_text("❌ Use: /maintenance on or /maintenance off")
    except Exception:
        await update.message.reply_text(f"Current Maintenance Status: {'ON' if MAINTENANCE_MODE else 'OFF'}\nUse: /maintenance on/off")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("❌ Format: /broadcast Your message here...")
        return

    users = get_all_users()
    success = 0
    failed = 0
    status_msg = await update.message.reply_text(f"⏳ Broadcasting to {len(users)} users...")

    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 Announcement / Update:\n\n{message_text}")
            success += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(f"✅ Broadcast Completed!\n\nSuccessful: {success}\nFailed: {failed}")

def get_main_keyboard():
    keyboard = [
        ["🛒 Buy Number"],
        ["💳 Deposit", "📞 Support"],
        ["👤 Profile", "📅 Today"],
        ["📜 History", "💸 Withdraw"]
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
    commands = [
        BotCommand("start", "🔄 Restart Bot / Show Menu"),
        BotCommand("users", "👥 View All Users & Balances (Admin)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAINTENANCE_MODE
    user = update.effective_user

    if MAINTENANCE_MODE and user.id != ADMIN_ID:
        await update.message.reply_text("🛠 Bot is under Maintenance! Please wait.")
        return

    get_user(user.id, user.username)
    context.user_data.clear()

    welcome_text = f"👋 Welcome, {user.first_name}!\n\nChoose an option below:"
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def show_buy_menu(update: Update):
    wa_count, wa_price = get_stock_info("whatsapp")
    tg_count, tg_price = get_stock_info("telegram")

    msg_text = (
        "🛒 Buy Number\n"
        "━━━━━━━\n"
        "Select the platform you need 👇\n\n"
        f"📱 WhatsApp — 📦 {wa_count} in stock • 💰 {wa_price:.2f} USDT\n"
        f"✈️ Telegram — 📦 {tg_count} in stock • 💰 {tg_price:.2f} USDT"
    )
    await update.message.reply_text(msg_text, reply_markup=get_platform_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAINTENANCE_MODE
    user = update.effective_user

    if MAINTENANCE_MODE and user.id != ADMIN_ID:
        await update.message.reply_text("🛠 Bot is under Maintenance! Please wait.")
        return

    text = update.message.text
    user_step = context.user_data.get("step")

    if text in ["❌ Cancel", "🔙 Back"]:
        if user_step == "waiting_for_bulk_qty":
            context.user_data["step"] = "purchase_type"
            await update.message.reply_text("🔙 Action cancelled.", reply_markup=get_purchase_type_keyboard())
            return
        elif user_step == "purchase_type":
            context.user_data["step"] = "category"
            await show_buy_menu(update)
            return
        else:
            context.user_data.clear()
            await update.message.reply_text("🔙 Main menu-te phire asha hoyeche.", reply_markup=get_main_keyboard())
            return

    if user_step == "waiting_for_bulk_qty":
        try:
            numbers_found = re.findall(r'\d+', text)
            if not numbers_found:
                await update.message.reply_text("❌ Doyakore sothik shongkha (Number) type korun:")
                return
            
            qty = int(numbers_found[0])
            if qty <= 0:
                await update.message.reply_text("❌ Porjapto quantity দিন (minimum 1).")
                return
            
            platform = context.user_data.get("selected_platform", "whatsapp")
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, item_data, price FROM stock WHERE item_type = %s LIMIT %s", (platform, qty))
            items = cursor.fetchall()

            if len(items) < qty:
                await update.message.reply_text(f"❌ Stock-e eto number nei! Available stock: {len(items)}", reply_markup=get_purchase_type_keyboard())
                cursor.close()
                conn.close()
                context.user_data["step"] = "purchase_type"
                return

            total_price = float(sum([item[2] for item in items]))
            user_balance = float(get_user(user.id, user.username))

            if user_balance < total_price:
                await update.message.reply_text(f"⚠️ Insufficient balance!\nRequired: ${total_price:.2f}, Your Balance:${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
                cursor.close()
                conn.close()
                context.user_data["step"] = "purchase_type"
                return

            update_balance(user.id, -total_price)
            
            item_texts = []
            for item in items:
                stock_id = item[0]
                item_data = str(item[1])
                price = float(item[2])
                
                item_texts.append(item_data)
                cursor.execute("DELETE FROM stock WHERE id = %s", (stock_id,))
                cursor.execute(
                    "INSERT INTO history (user_id, platform, item_data, price) VALUES (%s, %s, %s, %s)",
                    (user.id, platform, item_data, price)
                )

            conn.commit()
            cursor.close()
            conn.close()

            file_content = "\n".join(item_texts)
            file_name = f"{platform.upper()}_BULK_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(file_content)

            with open(file_name, "rb") as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=file_name),
                    caption=f"🎉 Bulk Purchase Successful!\n📦 Platform: {platform.upper()}\n🔢 Quantity: {qty}\n💰 Total Cost: ${total_price:.2f}",
                    reply_markup=get_purchase_type_keyboard()
                )
            
            os.remove(file_name)
            context.user_data["step"] = "purchase_type"
            return

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            context.user_data["step"] = "purchase_type"
            return

    if text == "1️⃣ Single Purchase":
        platform = context.user_data.get("selected_platform", "whatsapp")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_data, price FROM stock WHERE item_type = %s LIMIT 1", (platform,))
        stock_item = cursor.fetchone()

        if not stock_item:
            await update.message.reply_text(f"❌ Current {platform.upper()} stock is empty!", reply_markup=get_purchase_type_keyboard())
            cursor.close()
            conn.close()
            return

        stock_id = stock_item[0]
        item_data = str(stock_item[1])
        price = float(stock_item[2])
        user_balance = float(get_user(user.id, user.username))

        if user_balance < price:
            await update.message.reply_text(f"⚠️ Insufficient balance! Price: ${price:.2f}, Balance:${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
            cursor.close()
            conn.close()
            return

        update_balance(user.id, -price)
        cursor.execute("DELETE FROM stock WHERE id = %s", (stock_id,))
        cursor.execute(
            "INSERT INTO history (user_id, platform, item_data, price) VALUES (%s, %s, %s, %s)",
            (user.id, platform, item_data, price)
        )
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text(
            f"🎉 Single Purchase Successful!\n📦 Platform: {platform.upper()}\n🔑 Details:\n{item_data}",
            reply_markup=get_purchase_type_keyboard()
        )
        return

    if text == "📦 Bulk purchase":
        context.user_data["step"] = "waiting_for_bulk_qty"
        platform = context.user_data.get("selected_platform", "whatsapp")
        platform_title = "WhatsApp Numbers" if platform == "whatsapp" else "Telegram Numbers"
        count, price = get_stock_info(platform)
        user_balance = get_user(user.id, user.username)
        affordable = int(user_balance // price) if price > 0 else 0

        bulk_prompt = (
            f"📦 Bulk Purchase — {platform_title}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 In stock: {count} numbers\n"
            f"💰 Price: {price:.2f} USDT each\n"
            f"💳 Your balance: {user_balance:.3f} USDT\n"
            f"🔢 You can afford: {affordable} numbers\n\n"
            "✍️ How many numbers do you want?\n"
            f"Send a number between 1 and {min(count, affordable) if affordable > 0 else count}.\n\n"
            "Use /cancel or click button below to abort."
        )
        
        cancel_keyboard = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
        await update.message.reply_text(bulk_prompt, reply_markup=cancel_keyboard)
        return

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
            f"📱 {platform_title}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🇺🇸 USA +1 {platform.title()} Number Only\n\n"
            f"📦 Stock: {count} numbers\n"
            f"💰 Price: {price:.2f} USDT per number\n\n"
            "নাম্বারে ওটিপি না আসলে রিফান্ড পাবেন। বিস্তারিত না পড়ে নাম্বার কিনবেন না।\n"
            "Choose an option:"
        )
        await update.message.reply_text(msg_text, reply_markup=get_purchase_type_keyboard())

    elif text == "💳 Deposit":
        keyboard = [
            [InlineKeyboardButton("💳 bKash / Nagad", callback_data="pay_bkash")],
            [InlineKeyboardButton("🪙 Crypto (BEP-20 / USDT)", callback_data="pay_crypto")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💳 Select Deposit Method:", reply_markup=reply_markup)

    elif text == "📞 Support":
        support_text = (
            "📞 Customer Support & Help Desk\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 Admin Support: @Fbotphere\n"
            "📢 Update Channel: @TGNumberUpdate"
        )
        await update.message.reply_text(support_text)

    elif text == "👤 Profile":
        balance = get_user(user.id, user.username)
        profile_text = f"👤 User Profile:\n━━━━━━━━━━━\n🆔 ID: {user.id}\n👤 Username: @{user.username if user.username else 'N/A'}\n💰 Balance: ${balance:.2f} USDT"
        await update.message.reply_text(profile_text)

    elif text == "📅 Today":
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fixed Today query using TO_CHAR for accurate timezone comparison
        cursor.execute(
            "SELECT platform, item_data, price, purchase_date FROM history WHERE user_id = %s AND TO_CHAR(purchase_date, 'YYYY-MM-DD') = TO_CHAR(CURRENT_TIMESTAMP, 'YYYY-MM-DD') ORDER BY purchase_date DESC",
            (user.id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            await update.message.reply_text("📅 Today's History:\n\nAji apni kono number kenen ni.")
            return

        history_msg = "📅 Today's Purchase History:\n━━━━━━━━━━━━━━━━━━━━━\n"
        for row in rows:
            plat, data, prc, dt = row
            history_msg += f"📦 {plat.upper()} | 💰 ${prc:.2f}\n🔑 Data: {data}\n⏱ {dt}\n--------------------\n"
        await update.message.reply_text(history_msg)

    elif text == "📜 History":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT platform, item_data, price, purchase_date FROM history WHERE user_id = %s ORDER BY purchase_date DESC LIMIT 15",
            (user.id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            await update.message.reply_text("📜 Life-Time History:\n\nApnar kono purchase history nei.")
            return

        history_msg = "📜 Life-Time Purchase History (Last 15):\n━━━━━━━━━━━━━━━━━━━━━\n"
        for row in rows:
            plat, data, prc, dt = row
            history_msg += f"📦 {plat.upper()} | 💰 ${prc:.2f}\n🔑 Data: {data}\n⏱ {dt}\n--------------------\n"
        await update.message.reply_text(history_msg)

    elif text == "💸 Withdraw":
        await update.message.reply_text("💸 Balance porjapto noi. Withdraw er jonno minimum balance $10 hote hobe.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "pay_bkash":
        await query.edit_message_text(
            "📲 Mobile Banking Deposit\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🟢 bKash Personal: `01603282319`\n"
            "🟠 Nagad Personal: `01603282319`\n\n"
            f"⚠️ Niyom: Send Money korar por Admin-ke Transaction ID o apnar User ID ({user.id}) likhe message din."
        )
    elif data == "pay_crypto":
        await query.edit_message_text(
            "🪙 Crypto Deposit (BEP-20 / USDT)\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 Network: BNB Smart Chain (BEP20)\n"
            "💳 Wallet Address:\n`0x8f573aa283b98f570aacf3db0387b1c39118c29c`\n\n"
            f"⚠️ Niyom: Deposit korar por Admin-ke Transaction Hash/TXID o apnar User ID ({user.id}) likhe message din."
        )

def main():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", admin_users_command)) # Notun admin command
    application.add_handler(CommandHandler("add", add_stock))
    application.add_handler(CommandHandler("addbal", add_bal))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot started with fixed Today button and /users command...")
    application.run_polling()

if __name__ == "__main__":
    main()