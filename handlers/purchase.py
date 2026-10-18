import os
import re
from datetime import datetime
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db_connection, get_user, update_balance, get_stock_info
from utils import notify_channel_purchase

def get_purchase_type_keyboard():
    keyboard = [
        ["1️⃣ Single Purchase", "📦 Bulk purchase"],
        ["🔙 Back"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def handle_bulk_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    try:
        numbers_found = re.findall(r'\d+', text)
        if not numbers_found:
            await update.message.reply_text("❌ Doyakore sothik shongkha (Number) type korun:")
            return
        
        qty = int(numbers_found[0])
        if qty <= 0:
            await update.message.reply_text("❌ Porjapto quantity din (minimum 1).")
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
            await update.message.reply_text(f"⚠️ Insufficient balance!\nRequired: ${total_price:.2f}, Your Balance: ${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
            cursor.close()
            conn.close()
            context.user_data["step"] = "purchase_type"
            return

        update_balance(user.id, -total_price)
        
        item_texts = []
        unit_price = items[0][2] if items else 0.0
        first_number = items[0][1] if items else ""

        for item in items:
            stock_id = item[0]
            item_data = str(item[1])
            price = float(item[2])
            
            item_texts.append(item_data)
            cursor.execute("DELETE FROM stock WHERE id = %s", (stock_id,))
            cursor.execute(
                "INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (%s, %s, %s, %s, NOW())",
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

        await notify_channel_purchase(context, user.id, platform, qty, unit_price, first_number)
        return

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        context.user_data["step"] = "purchase_type"
        return

async def handle_single_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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
        await update.message.reply_text(f"⚠️ Insufficient balance! Price: ${price:.2f}, Balance: ${user_balance:.2f}", reply_markup=get_purchase_type_keyboard())
        cursor.close()
        conn.close()
        return

    update_balance(user.id, -price)
    cursor.execute("DELETE FROM stock WHERE id = %s", (stock_id,))
    cursor.execute(
        "INSERT INTO history (user_id, platform, item_data, price, purchase_date) VALUES (%s, %s, %s, %s, NOW())",
        (user.id, platform, item_data, price)
    )
    conn.commit()
    cursor.close()
    conn.close()

    await update.message.reply_text(
        f"🎉 Single Purchase Successful!\n📦 Platform: {platform.upper()}\n🔑 Details:\n{item_data}",
        reply_markup=get_purchase_type_keyboard()
    )

    await notify_channel_purchase(context, user.id, platform, 1, price, item_data)
    return