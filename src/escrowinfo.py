import logging
import os # Added for environment variable access
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from oneshot import oneshot_client, BUSINESS_ID
from helpers import get_chain_id_from_network_name # To translate network name to chain_id

logger = logging.getLogger(__name__)

async def show_escrow_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the primary escrow wallet."""
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="Fetching your escrow wallet information...")

    try:
        # Determine the chain_id to query for.
        # Default to Sepolia if ONESHOT_NETWORK is not set, as main.py startup ensures a Sepolia wallet.
        network_name = os.getenv("ONESHOT_NETWORK", "sepolia").lower()
        chain_id_to_query = get_chain_id_from_network_name(network_name)

        if not chain_id_to_query:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Could not determine a valid chain ID for network: {network_name}. Please check bot configuration or ONESHOT_NETWORK environment variable."
            )
            return

        wallets_response = await oneshot_client.wallets.list(
            business_id=BUSINESS_ID, 
            params={"chain_id": chain_id_to_query} # Filter by the determined network's chain ID
        )

        if wallets_response and wallets_response.response and len(wallets_response.response) > 0:
            escrow_wallet = wallets_response.response[0]
            wallet_id = escrow_wallet.id
            wallet_address = escrow_wallet.address
            
            balance_str = "N/A"
            if escrow_wallet.account_balance_details and escrow_wallet.account_balance_details.balance is not None:
                raw_balance = escrow_wallet.account_balance_details.balance 
                currency_symbol = escrow_wallet.account_balance_details.currency_symbol or network_name.upper()
                balance_str = f"{raw_balance} {currency_symbol}"

            info_message = (
                f"✨ **Your 1Shot Escrow Wallet Information** ✨\n\n"
                f"**Network:** {network_name.capitalize()} (Chain ID: {chain_id_to_query})\n"
                f"**Wallet ID:** `{wallet_id}`\n"
                f"**Address:** `{wallet_address}`\n"
                f"**Balance:** {balance_str}\n"
            )
            await context.bot.send_message(chat_id=chat_id, text=info_message, parse_mode=ParseMode.MARKDOWN)
        elif wallets_response and wallets_response.error:
            logger.error(f"Error fetching escrow wallets: {wallets_response.error.message}")
            await context.bot.send_message(chat_id=chat_id, text=f"Could not retrieve escrow wallet info: {wallets_response.error.message}")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"No escrow wallet found configured for your business on network '{network_name}' (Chain ID: {chain_id_to_query}).")

    except Exception as e:
        logger.error(f"Exception in show_escrow_info: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text=f"An unexpected error occurred while fetching escrow info: {e}")

def get_escrow_info_handler() -> CommandHandler:
    """Returns a CommandHandler for the /myescrowinfo command."""
    return CommandHandler("myescrowinfo", show_escrow_info)
