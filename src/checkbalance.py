# checkbalance.py

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from oneshot import oneshot_client, BUSINESS_ID

logger = logging.getLogger(__name__)

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check the balance of a wallet address."""
    try:
        # If no address provided, check the escrow wallet balance
        if not context.args:
            wallets = await oneshot_client.wallets.list(
                BUSINESS_ID,
                {"chain_id": "11155111"}  # Sepolia testnet
            )
            
            if not wallets.response:
                await update.message.reply_text(
                    "❌ No escrow wallet found. Please contact support.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            balance = float(wallets.response[0].account_balance_details.balance)
            address = wallets.response[0].address
            
            message = (
                "💰 *Escrow Wallet Balance*\n\n"
                f"*Address:* `{address}`\n"
                f"*Balance:* {balance:.6f} ETH\n"
                "━━━━━━━━━━━━━━━"
            )
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # If address provided, check that specific address
        address = context.args[0]
        if not address.startswith("0x") or len(address) != 42:
            await update.message.reply_text(
                "❌ Invalid Ethereum address format. Please provide a valid address starting with '0x'.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Get balance for the specified address
        wallets = await oneshot_client.wallets.list(
            BUSINESS_ID,
            {"chain_id": "11155111", "address": address}
        )
        
        if not wallets.response:
            await update.message.reply_text(
                "❌ No wallet found with the provided address.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        balance = float(wallets.response[0].account_balance_details.balance)
        
        message = (
            "💰 *Wallet Balance*\n\n"
            f"*Address:* `{address}`\n"
            f"*Balance:* {balance:.6f} ETH\n"
            "━━━━━━━━━━━━━━━"
        )
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        await update.message.reply_text(
            "❌ An error occurred while checking the balance.",
            parse_mode=ParseMode.MARKDOWN
        )
