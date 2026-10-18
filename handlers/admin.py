from telegram import Update, InputFile
from telegram.ext import ContextTypes
from config import ADMIN_ID
import config
from database import get_db_connection, update_balance, get_all_users
from utils import notify_channel_deposit
import logging

logger = logging.getLogger(__name__)

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
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
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
        return

    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ শুধু .txt ফাইল আপলোড করুন!")
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
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
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

        await notify_channel_deposit(context, target_user_id, amount)

    except Exception:
        await update.message.reply_text("❌ Format: /addbal USER_ID AMOUNT")

async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        await update.message.reply_text("📁 ডাটাবেজে কোনো ইউজার নেই।")
        return

    msg = "👥 **All Registered Users & Balances:**\n━━━━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        uid, uname, bal = row
        msg += f"🆔 ID: `{uid}`\n👤 @{uname if uname else 'N/A'}\n💰 Balance: `${bal:.2f}`\n--------------------\n"
    
    if len(msg) > 4000:
        msg = msg[:4000] + "\n... (list too long)"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
        return
    
    try:
        status = context.args[0].lower()
        if status == "on":
            config.MAINTENANCE_MODE = True
            await update.message.reply_text("⚠️ Bot is now in Maintenance Mode.")
        elif status == "off":
            config.MAINTENANCE_MODE = False
            await update.message.reply_text("✅ Bot is now Live / Active.")
        else:
            await update.message.reply_text("❌ Use: /maintenance on or /maintenance off")
    except Exception:
        await update.message.reply_text(f"Current Maintenance Status: {'ON' if config.MAINTENANCE_MODE else 'OFF'}\nUse: /maintenance on/off")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
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