# checkbalance.py

import os
from telegram import Update
from telegram.ext import ContextTypes
import requests

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Lütfen bir cüzdan adresi girin.\nÖrn: `/checkbalance 0xabc...`", parse_mode="Markdown")
        return

    address = context.args[0]
    api_key = os.getenv("ONESHOT_API_KEY")
    business_id = os.getenv("ONESHOT_BUSINESS_ID")

    try:
        url = f"https://api.1shotapi.com/wallets/{address}/balance"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Business-ID": business_id,
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        balance = data.get("balance", "0")
        await update.message.reply_text(f"💰 `{address}`\nBakiyesi: *{balance} ETH*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Bakiye sorgularken hata oluştu.")
        print(f"checkbalance error: {e}")
