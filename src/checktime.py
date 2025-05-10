from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the current time when the command /time is issued."""
    current_time = datetime.now().strftime("%H:%M:%S")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    await update.message.reply_text(
        f"🕒 Current time: *{current_time}*\n"
        f"📅 Date: *{current_date}*",
        parse_mode="Markdown"
    ) 