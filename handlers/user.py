from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import config
from config import ADMIN_ID
from database import get_user, get_stock_info, get_db_connection
from handlers.purchase import get_purchase_type_keyboard, handle_bulk_purchase, handle_single_purchase

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if config.MAINTENANCE_MODE and user.id != ADMIN_ID:
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
    user = update.effective_user

    if config.MAINTENANCE_MODE and user.id != ADMIN_ID:
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
        await handle_bulk_purchase(update, context)
        return

    if text == "1️⃣ Single Purchase":
        await handle_single_purchase(update, context)
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
            "📢 Update Channel: @TGnumbeupdate"
        )
        await update.message.reply_text(support_text)

    elif text == "👤 Profile":
        balance = get_user(user.id, user.username)
        profile_text = f"👤 User Profile:\n━━━━━━━━━━━\n🆔 ID: {user.id}\n👤 Username: @{user.username if user.username else 'N/A'}\n💰 Balance: ${balance:.2f} USDT"
        await update.message.reply_text(profile_text)

    elif text == "📅 Today":
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Absolute bulletproof fix: Fetch user's history and filter in Python based on Bangladesh local date
        cursor.execute(
            "SELECT platform, item_data, price, purchase_date FROM history WHERE user_id = %s ORDER BY purchase_date DESC LIMIT 30",
            (user.id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Get current Bangladesh date string (YYYY-MM-DD)
        bd_today = (datetime.utcnow() + timedelta(hours=6)).strftime("%Y-%m-%d")
        
        today_rows = []
        for row in rows:
            plat, data, prc, dt = row
            if isinstance(dt, datetime):
                # Convert database UTC timestamp to Bangladesh local timestamp
                dt_bd = dt + timedelta(hours=6)
                if dt_bd.strftime("%Y-%m-%d") == bd_today:
                    today_rows.append((plat, data, prc, dt_bd))

        if not today_rows:
            await update.message.reply_text("📅 Today's History:\n\nAji apni kono number kenen ni.")
            return

        history_msg = "📅 Today's Purchase History:\n━━━━━━━━━━━━━━━━━━━━━\n"
        for row in today_rows:
            plat, data, prc, dt_bd = row
            dt_str = dt_bd.strftime("%d-%m-%Y %I:%M:%S %p")
            history_msg += f"📦 {plat.upper()} | 💰 ${prc:.2f}\n🔑 Data: {data}\n⏱ {dt_str}\n--------------------\n"
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
            # Convert lifetime display also to BD time
            dt_bd = dt + timedelta(hours=6) if isinstance(dt, datetime) else dt
            dt_str = dt_bd.strftime("%d-%m-%Y %I:%M:%S %p") if isinstance(dt_bd, datetime) else str(dt_bd)
            history_msg += f"📦 {plat.upper()} | 💰 ${prc:.2f}\n🔑 Data: {data}\n⏱ {dt_str}\n--------------------\n"
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