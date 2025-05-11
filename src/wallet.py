import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

logger = logging.getLogger(__name__)

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show wallet balance."""
    try:
        # Mock balance of 10,000 ETH
        balance = 10000.0
        
        # Format the message with emojis and proper formatting
        message = (
            "💰 *Wallet Balance*\n\n"
            f"*Balance:* {balance:,.2f} ETH\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 This is a mock balance for demonstration purposes."
        )
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in wallet command: {e}")
        await update.message.reply_text(
            "❌ Sorry, an error occurred while fetching your wallet balance."
        )

def get_wallet_handler() -> CommandHandler:
    """Create and return the wallet command handler."""
    return CommandHandler("wallet", wallet) 