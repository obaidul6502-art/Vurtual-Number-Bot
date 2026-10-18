import random
import string
from datetime import datetime
from database import get_total_users_balance
from config import UPDATE_CHANNEL

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
    return f"{prefix}-*****{mid}S{suffix}"

async def notify_channel_purchase(context, user_id, platform, qty, unit_price, number_sample):
    try:
        total_bot_bal = get_total_users_balance()
        now_str = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        masked_uid = mask_user_id(user_id)
        masked_num = mask_number(number_sample)
        order_id = generate_order_id()

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
        print(f"Failed to post purchase notification: {str(e)}")

async def notify_channel_deposit(context, user_id, amount):
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
        print(f"Failed to post deposit notification: {str(e)}")