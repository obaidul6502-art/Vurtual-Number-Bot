import os
import logging
import re
import random
import string
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import TOKEN, ADMIN_ID, UPDATE_CHANNEL, DATABASE_URL, MAINTENANCE_MODE
from database import get_db_connection, init_db, get_user, update_balance, get_all_users, get_stock_info, get_total_users_balance

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

def init_settings_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing settings table: {str(e)}")

init_settings_table()

def get_main_keyboard():
    keyboard = [
        ["🛒 Buy Number"],
        ["💳 Deposit", "📞 Support"],
        ["👤 Profile", "📅 Today"],
        ["📜 History", "📚 Method"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_purchase_type_keyboard():
    keyboard = [
        ["1️⃣ Single Purchase", "📦 Bulk purchase"],
        ["🔙 Back"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=UPDATE_CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Update Channel", url=f"https://t.me/{UPDATE_CHANNEL.replace('@', '')}")],
        [InlineKeyboardButton("🔄 Check Membership", callback_data="check_sub")]
    ])
    await update.message.reply_text(
        f"⚠️ **Channel Membership Required!**\n\nPlease join our update channel {UPDATE_CHANNEL} first to use this bot features.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return False

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "check_sub":
        user_id = query.from_user.id
        try:
            member = await context.bot.get_chat_member(chat_id=UPDATE_CHANNEL, user_id=user_id)
            if member.status in ['member', 'administrator', 'creator']:
                await query.message.edit_text("✅ Thank you for joining! You can now use the bot.", reply_markup=None)
                await query.message.reply_text("🔙 Main menu:", reply_markup=get_main_keyboard())
            else:
                await query.answer("❌ You haven't joined the channel yet!", show_alert=True)
        except Exception:
            await query.answer("❌ Error checking membership. Please try again.", show_alert=True)

def mask_user_id(uid):
    s = str(uid)
    if len(s) >= 6:
        return f"{s[:3]}****{s[-3:]}"
    return f"{s[:2]}****"

def mask_number(num_str):
    num = num_str.strip().split()[0]
    if len(num) >= 7:
        return f"{num[:4]}****{num[-4:]}"
    return num

def generate_order_id():
    prefix = "".join(random.choices(string.digits, k=3))
    mid = "".join(random.choices(string.ascii_letters + string.digits, k=5))
    suffix = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"{prefix}-{mid}S{suffix}"

async def notify_channel_purchase(context: ContextTypes.DEFAULT_TYPE, user_id, platform, qty, unit_price, number_sample, specific_order_id=None):
    try:
        total_bot_bal = get_total_users_balance()
        now_str = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        masked_uid = mask_user_id(user_id)
        masked_num = mask_number(number_sample)
        order_id = specific_order_id if specific_order_id else generate_order_id()

        msg = (
            "Order History\n"
            "🎉 **New Purchase Successful!**\n\n"
            f"✈️ **Platform:** {platform.title()} USA\n"
            f"🆔 **User ID:** `{masked_uid}`\n"
            f"📊 **Quantity:** {qty} pcs\n"
            f"💵 **Price:** USDT {unit_price:.2f}\n"
            f"📱 **Number:** `{masked_num}`\n"
            f"🆔 **Order ID:** `{order_id}`\n"
            f"💰 **Total Bot Balance:** USDT {total_bot_bal:,.2f}\n"
            f"⏰ **Time:** {now_str}"
        )
        await context.bot.send_message(chat_id=UPDATE_CHANNEL, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to post purchase notification: {str(e)}")

async def notify_channel_deposit(context: ContextTypes.DEFAULT_TYPE, user_id, amount):
    try:
        now_str = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        masked_uid = mask_user_id(user_id)
        trx_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=4)) + "C0xxxxx"

        msg = (
            "Order History\n"
            "✅ **New Deposit Approved!**\n\n"
            f"👤 **User:** `{masked_uid}`\n"
            f"🔑 **TrxID:** `{trx_id}`\n"
            f"💵 **Amount:** {amount:.1f} USDT\n"
            f"📅 **Date:** {now_str}\n"
            f"✅ **Status:** Completed"
        )
        await context.bot.send_message(chat_id=UPDATE_CHANNEL, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to post deposit notification: {str(e)}")

# ADMIN COMMAND TO SET METHOD LINK: /setmethod ...
async def set_method_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    try:
        method_text = " ".join(context.args)
        if not method_text:
            await update.message.reply_text("❌ Format: /setmethod Your link or instructions here")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        if DATABASE_URL:
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", ("work_method", method_text))
        else:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("work_method", method_text))
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text(f"✅ Method successfully updated!\n\n{method_text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ADMIN COMMAND TO DELETE METHOD LINK: /delmethod
async def del_method_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Apni admin non!")
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        cursor.execute(f"DELETE FROM settings WHERE key = {ph}", ("work_method",))
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text("🗑️ Work method link has been deleted successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

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
        ph = "%s" if DATABASE_URL else "?"
        cursor.execute(f"INSERT INTO stock (item_type, item_data, price) VALUES ({ph}, {ph}, {ph})", (item_type, item_data, price))
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
        ph = "%s" if DATABASE_URL else "?"
        for line in lines:
            cursor.execute(f"INSERT INTO stock (item_type, item_data, price) VALUES ({ph}, {ph}, {ph})", (item_type, line, price))
        conn.commit()
        cursor.close()
        conn.close()

        await update.message.reply_text(f"🎉 Bulk Import Success!\n📦 Category: {item_type}\n🔢 Total Added: {len(lines)}")
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
        
        if amount > 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            if DATABASE_URL:
                cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (%s, %s, %s, %s, NOW())", (target_user_id, "deposit", f"Deposit Approved: ${amount}", amount))
            else:
                cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (?, ?, ?, ?, DATETIME('now'))", (target_user_id, "deposit", f"Deposit Approved: ${amount}", amount))
            conn.commit()
            cursor.close()
            conn.close()

        await update.message.reply_text(f"✅ Added ${amount} to User ID: {target_user_id}")
        await notify_channel_deposit(context, target_user_id, amount)

        try:
            user_msg = (
                "✅ **Deposit Approved Successfully!**\n\n"
                f"💵 **Amount Added:** `${amount:.2f}` USDT\n"
                "🎉 Your balance has been updated. You can now buy numbers!"
            )
            await context.bot.send_message(chat_id=target_user_id, text=user_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send deposit confirmation to user {target_user_id}: {str(e)}")

    except Exception:
        await update.message.reply_text("❌ Format: /addbal USER_ID AMOUNT")

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
        await update.message.reply_text("👥 Kono user paowa jayni.")
        return

    msg = "👥 **All Users List & Balance:**\n━━━━━━━━━━━━━━━━━━━━━\n"
    for r in rows:
        username_str = f"@{r[1]}" if r[1] else "No Username"
        msg += f"🆔 ID: `{r[0]}` | {username_str}\n💰 Balance: `${r[2]:.2f}` USDT\n--------------------\n"
    
    await update.message.reply_text(msg[:4000], parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username)
    context.user_data.clear()
    await update.message.reply_text(f"👋 Welcome, {user.first_name}!", reply_markup=get_main_keyboard())

async def show_buy_menu(update: Update):
    wa_count, wa_price = get_stock_info("whatsapp")
    tg_count, tg_price = get_stock_info("telegram")
    msg = f"🛒 Buy Number\n\n📱 WhatsApp — 📦 {wa_count} in stock • 💰 {wa_price:.2f} USDT\n✈️ Telegram — 📦 {tg_count} in stock • 💰 {tg_price:.2f} USDT"
    keyboard = [["📱 WhatsApp", "✈️ Telegram"], ["🔙 Back"]]
    return msg, ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    user_step = context.user_data.get("step")

    if text == "/users":
        await admin_users_command(update, context)
        return

    if text in ["❌ Cancel", "🔙 Back"]:
        context.user_data.clear()
        await update.message.reply_text("🔙 Main menu-te phire asha hoyeche.", reply_markup=get_main_keyboard())
        return

    # BULK PURCHASE QUANTITY INPUT HANDLER
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
            ph = "%s" if DATABASE_URL else "?"
            
            cursor.execute(f"SELECT id, item_data, price FROM stock WHERE item_type = {ph} LIMIT {ph}", (platform, qty))
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
                stock_id, item_data, price = item[0], str(item[1]), float(item[2])
                item_texts.append(item_data)
                cursor.execute(f"DELETE FROM stock WHERE id = {ph}", (stock_id,))
                if DATABASE_URL:
                    cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (%s, %s, %s, %s, NOW())", (user.id, platform, item_data, price))
                else:
                    cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (?, ?, ?, ?, DATETIME('now'))", (user.id, platform, item_data, price))

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
            
            if os.path.exists(file_name):
                os.remove(file_name)
                
            shared_order_id = generate_order_id()
            unit_price_avg = total_price / qty if qty > 0 else 0
            await notify_channel_purchase(context, user.id, platform, qty, unit_price_avg, item_texts[0], specific_order_id=shared_order_id)
            
            context.user_data["step"] = "purchase_type"
            return

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            context.user_data["step"] = "purchase_type"
            return

    if text == "📦 Bulk purchase":
        if not await check_subscription(update, context):
            return
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
            "Click ❌ Cancel button to abort."
        )
        
        cancel_keyboard = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
        await update.message.reply_text(bulk_prompt, reply_markup=cancel_keyboard)
        return

    elif text == "🛒 Buy Number":
        if not await check_subscription(update, context):
            return
        context.user_data["step"] = "category"
        msg, kb = await show_buy_menu(update)
        await update.message.reply_text(msg, reply_markup=kb)

    elif text in ["📱 WhatsApp", "✈️ Telegram"]:
        if not await check_subscription(update, context):
            return
        platform = "whatsapp" if "WhatsApp" in text else "telegram"
        context.user_data["selected_platform"] = platform
        context.user_data["step"] = "purchase_type"
        count, price = get_stock_info(platform)
        await update.message.reply_text(f"📦 Stock: {count} | Price: ${price:.2f}", reply_markup=get_purchase_type_keyboard())

    elif text == "1️⃣ Single Purchase":
        if not await check_subscription(update, context):
            return
        platform = context.user_data.get("selected_platform", "whatsapp")
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        cursor.execute(f"SELECT id, item_data, price FROM stock WHERE item_type = {ph} LIMIT 1", (platform,))
        stock_item = cursor.fetchone()
        if not stock_item:
            await update.message.reply_text(f"❌ Stock empty!")
            cursor.close()
            conn.close()
            return
        stock_id, item_data, price = stock_item[0], str(stock_item[1]), float(stock_item[2])
        user_balance = get_user(user.id, user.username)
        if user_balance < price:
            await update.message.reply_text(f"⚠️ Insufficient balance!")
            cursor.close()
            conn.close()
            return
        update_balance(user.id, -price)
        cursor.execute(f"DELETE FROM stock WHERE id = {ph}", (stock_id,))
        if DATABASE_URL:
            cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (%s, %s, %s, %s, NOW())", (user.id, platform, item_data, price))
        else:
            cursor.execute("INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (?, ?, ?, ?, DATETIME('now'))", (user.id, platform, item_data, price))
        conn.commit()
        cursor.close()
        conn.close()

        shared_order_id = generate_order_id()
        time_str = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        platform_name = platform.title()
        
        parts = item_data.split()
        phone_num = parts[0]
        otp_link = parts[1] if len(parts) > 1 and "http" in parts[1] else f"http://169.58.215.134:11111/sms/{platform.lower()}-{shared_order_id.lower()}"

        receipt_msg = (
            f"1️⃣ Single Purchase — {platform_name}\n"
            "🎁 Purchase Successful!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 Platform: {platform_name}\n"
            f"🆔 Order ID: `{shared_order_id}`\n"
            f"📱 Number: `{phone_num}`\n"
            f"🔗 Link: {otp_link}\n"
            f"💵 Price: {price:.2f} USDT\n"
            f"⏰ Time: {time_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 Tap below to get your OTP"
        )

        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Get OTP", url=otp_link if otp_link.startswith("http") else f"https://t.me/{UPDATE_CHANNEL.replace('@', '')}")]
        ])

        await update.message.reply_text(receipt_msg, reply_markup=inline_kb, parse_mode="Markdown")
        await notify_channel_purchase(context, user.id, platform, 1, price, item_data, specific_order_id=shared_order_id)

    elif text == "👤 Profile":
        if not await check_subscription(update, context):
            return
        bal = get_user(user.id, user.username)
        full_name = user.full_name if user.full_name else "N/A"
        username_str = f"@{user.username}" if user.username else "No Username"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        
        cursor.execute(f"SELECT COUNT(*), SUM(price) FROM history WHERE user_id = {ph} AND platform != 'deposit'", (user.id,))
        h_row = cursor.fetchone()
        total_purchased = h_row[0] if h_row and h_row[0] else 0
        total_spent = float(h_row[1]) if h_row and h_row[1] else 0.0

        cursor.execute(f"SELECT SUM(price) FROM history WHERE user_id = {ph} AND platform = 'deposit'", (user.id,))
        d_row = cursor.fetchone()
        total_deposit = float(d_row[0]) if d_row and d_row[0] else 0.0

        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(f"SELECT purchase_date FROM history WHERE user_id = {ph} AND platform != 'deposit'", (user.id,))
        all_dates = cursor.fetchall()
        today_usage = sum(1 for d in all_dates if today_str in str(d[0]))

        cursor.close()
        conn.close()

        profile_msg = (
            "👤 **User Profile**\n\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"👤 **Full Name:** {full_name}\n"
            f"📝 **Username:** {username_str}\n"
            "🚦 **Status:** 🟢 Approved\n"
            f"💰 **Balance:** {bal:.3f}\n"
            f"💎 **Total Available:** {bal:.4f} USDT (🛒 {bal:.4f} + 👥 0.0000)\n"
            "⏳ **Hold Balance:** 0 USDT\n"
            f"📊 **Total Purchased:** {total_purchased}\n"
            f"💵 **Total Spent:** {total_spent:.2f}\n"
            f"💳 **Total Deposit:** {int(total_deposit) if total_deposit.is_integer() else total_deposit}\n"
            f"✅ **Total OTP Received:** {total_purchased}\n"
            "📈 **OTP Ratio:** 100.0%\n"
            f"📅 **Today's Usage:** {today_usage}\n"
            "⌛ **Pending Tasks:** 0/3"
        )
        await update.message.reply_text(profile_msg, parse_mode="Markdown")

    elif text == "📅 Today":
        if not await check_subscription(update, context):
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        cursor.execute(f"SELECT platform, item_data, price, purchase_date FROM history WHERE user_id = {ph} AND platform != 'deposit' ORDER BY purchase_date DESC", (user.id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_rows = [r for r in rows if today_str in str(r[3])]

        if not today_rows:
            await update.message.reply_text("📅 Today's History:\n\nAji apni kono number kenen ni.")
            return

        msg = "📅 Today's Purchase History:\n━━━━━━━━━━━━━━━━━━━━━\n"
        for r in today_rows:
            msg += f"📦 {r[0].upper()} | 💰 ${r[2]:.2f}\n🔑 Data: {r[1]}\n⏱ {r[3]}\n--------------------\n"
        await update.message.reply_text(msg)

    elif text == "📜 History":
        if not await check_subscription(update, context):
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = "%s" if DATABASE_URL else "?"
        cursor.execute(f"SELECT platform, item_data, price, purchase_date FROM history WHERE user_id = {ph} AND platform != 'deposit' ORDER BY purchase_date DESC", (user.id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            await update.message.reply_text("📜 Life-Time Purchase History is empty.")
            return

        msg = "📜 **Life-Time Purchase History:**\n━━━━━━━━━━━━━━━━━━━━━\n"
        for r in rows:
            msg += f"📦 {r[0].upper()} | 💰 ${r[2]:.2f}\n🔑 Data: {r[1]}\n⏱ {r[3]}\n--------------------\n"
            
        if len(msg) > 4000:
            file_name = f"Lifetime_History_{user.id}.txt"
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(msg.replace("*", "").replace("━━━━━━━━━━━━━━━━━━━━━", "---------------------"))
            with open(file_name, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=file_name), caption="📜 Your Life-Time Purchase History file.")
            if os.path.exists(file_name):
                os.remove(file_name)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "💳 Deposit":
        if not await check_subscription(update, context):
            return
        deposit_kb = ReplyKeyboardMarkup([
            ["bKash/Nagad", "Binance"],
            ["❌ Cancel"]
        ], resize_keyboard=True)
        await update.message.reply_text("💳 Please select your deposit method:", reply_markup=deposit_kb)
        return

    elif text == "bKash/Nagad":
        if not await check_subscription(update, context):
            return
        bkash_msg = "💳 **bKash/Nagad Deposit:**\n\nSend money to: `01603282319` (Personal)\nAfter sending money, send TrxID to admin @Fbotphere."
        await update.message.reply_text(bkash_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    elif text == "Binance":
        if not await check_subscription(update, context):
            return
        binance_msg = "💳 **Binance Pay Deposit:**\n\nBinance Pay ID / USDT TRC20 Address: `YourBinanceWalletAddressHere`\nAfter payment, send TXID / Screenshot to admin @Fbotphere."
        await update.message.reply_text(binance_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    elif text == "📚 Method":
        if not await check_subscription(update, context):
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            ph = "%s" if DATABASE_URL else "?"
            cursor.execute(f"SELECT value FROM settings WHERE key = {ph}", ("work_method",))
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            method_content = row[0] if row else "⚠️ No work method or instructions have been set by the admin yet."
            
            method_msg = (
                "📚 **Work Methods & Guidelines:**\n\n"
                f"{method_content}"
            )
            await update.message.reply_text(method_msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"📚 **Work Methods & Guidelines:**\n\n⚠️ Error loading method: {str(e)}")
        return

    elif text == "📞 Support":
        await update.message.reply_text("📞 Admin: @Fbotphere")

def main():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", admin_users_command))
    application.add_handler(CommandHandler("add", add_stock))
    application.add_handler(CommandHandler("addbal", add_bal))
    application.add_handler(CommandHandler("setmethod", set_method_command))
    application.add_handler(CommandHandler("delmethod", del_method_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running with /setmethod and /delmethod commands...")
    application.run_polling()

if __name__ == "__main__":
    main()