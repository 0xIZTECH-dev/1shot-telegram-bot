import logging
from decimal import Decimal, InvalidOperation
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from helpers import convert_to_wei, format_wei, get_chain_id_from_network_name
from oneshot import oneshot_client
from objects import TxType, TransactionMemo

logger = logging.getLogger(__name__)

# Conversation states
SELECT_ACTION, \
ENTER_RECIPIENT_NATIVE, ENTER_AMOUNT_NATIVE, CONFIRM_NATIVE_TRANSFER, \
SELECT_BALANCE_TYPE, ENTER_TOKEN_ADDRESS_FOR_BALANCE = range(6)

async def transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the transaction conversation and asks for action choice."""
    keyboard = [
        ["Transfer Native Currency (Escrow)"],
        ["Check Escrow Wallet Balance"],
        ["Check Specific Token Balance"],
        ["Cancel"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "What would you like to do with transactions? Please choose:",
        reply_markup=reply_markup,
    )
    return SELECT_ACTION

async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice from the main transaction menu."""
    user_choice = update.message.text
    context.user_data['transaction_choice'] = user_choice

    if user_choice == "Transfer Native Currency (Escrow)":
        await update.message.reply_text(
            "Okay, let's transfer native currency from your escrow wallet.\n"
            "Please enter the recipient's address:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ENTER_RECIPIENT_NATIVE
    elif user_choice == "Check Escrow Wallet Balance":
        return await check_escrow_balance(update, context)
    elif user_choice == "Check Specific Token Balance":
        await update.message.reply_text(
            "Please enter the token contract address to check its balance:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ENTER_TOKEN_ADDRESS_FOR_BALANCE
    elif user_choice == "Cancel":
        return await cancel(update, context)
    else:
        await update.message.reply_text("Invalid choice. Please try again or type /cancel.")
        return SELECT_ACTION


# --- Native Currency Transfer from Escrow ---
async def prompt_recipient_native(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores recipient address and asks for amount for native transfer."""
    recipient_address = update.message.text
    if not recipient_address.startswith("0x") or len(recipient_address) != 42: # Basic validation
        await update.message.reply_text("Invalid address format. Please enter a valid Ethereum address (e.g., 0x...).")
        return ENTER_RECIPIENT_NATIVE
    context.user_data['recipient_address'] = recipient_address
    await update.message.reply_text("Great. Now, please enter the amount of native currency to transfer (e.g., 0.1):")
    return ENTER_AMOUNT_NATIVE

async def prompt_amount_native(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores amount, shows confirmation for native transfer."""
    try:
        amount_str = update.message.text
        amount_decimal = Decimal(amount_str)
        if amount_decimal <= 0:
            raise ValueError("Amount must be positive.")
        context.user_data['amount_native'] = amount_str # Store as string for display, convert to wei later

        recipient_address = context.user_data['recipient_address']
        confirmation_message = (
            f"You are about to transfer {amount_str} native currency\n"
            f"from your escrow wallet to: {recipient_address}.\n\n"
            "Type 'yes' to confirm, or 'no' to cancel."
        )
        await update.message.reply_text(confirmation_message)
        return CONFIRM_NATIVE_TRANSFER
    except (InvalidOperation, ValueError) as e:
        logger.error(f"Invalid amount entered: {update.message.text} - {e}")
        await update.message.reply_text(
            "Invalid amount. Please enter a valid positive number (e.g., 0.1 or 10)."
        )
        return ENTER_AMOUNT_NATIVE

async def confirm_native_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirms and executes native currency transfer from escrow."""
    user_response = update.message.text.lower()
    if user_response == 'yes':
        try:
            recipient_address_val = context.user_data['recipient_address']
            amount_str_val = context.user_data['amount_native']
            amount_wei = convert_to_wei(amount_str_val, decimals=18) # Native currency typically has 18 decimals

            network_name = oneshot_client.network
            chain_id = get_chain_id_from_network_name(network_name)
            if not chain_id:
                await update.message.reply_text("Could not determine the chain ID for the transaction. Please check bot configuration.")
                return ConversationHandler.END

            memo = TransactionMemo(
                tx_type=TxType.NATIVE_CURRENCY_TRANSFER,
                associated_user_id=update.effective_user.id,
                chat_id=update.effective_chat.id, # Added chat_id
                recipient_address=recipient_address_val, # Added recipient_address
                amount_readable=amount_str_val, # Added amount_readable
                note_to_user=f"Native transfer of {amount_str_val} to {recipient_address_val}"
            )

            await update.message.reply_text("Processing your transfer...")

            transaction_execution = await oneshot_client.transactions.create_transaction_from_escrow_wallet(
                chain_id=str(chain_id),
                to_address=recipient_address_val,
                value=str(amount_wei), # SDK expects string
                memo=memo.to_json_string()
            )

            if transaction_execution and transaction_execution.response and transaction_execution.response.id:
                tx_id = transaction_execution.response.id
                # The actual transaction hash might come via webhook. For now, acknowledge initiation.
                await update.message.reply_text(
                    f"Native currency transfer initiated! Transaction Execution ID: {tx_id}\n"
                    f"You will be notified once it's processed. The details will arrive via webhook."
                )
                logger.info(f"Native currency transfer from escrow initiated. Execution ID: {tx_id}")
            else:
                logger.error(f"Failed to initiate native transfer. Response: {transaction_execution.error if transaction_execution and transaction_execution.error else 'No response or unexpected response.'}")
                await update.message.reply_text(
                    "Sorry, there was an issue initiating the transfer. "
                    "Please try again later or contact support if the problem persists."
                )

        except Exception as e:
            logger.error(f"Error during native currency transfer: {e}", exc_info=True)
            await update.message.reply_text(f"An error occurred: {e}")
        return ConversationHandler.END
    elif user_response == 'no':
        await update.message.reply_text("Transfer cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        await update.message.reply_text("Invalid response. Please type 'yes' or 'no'.")
        return CONFIRM_NATIVE_TRANSFER

# --- Balance Checking ---
async def check_escrow_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetches and displays the escrow wallet's native currency balance."""
    try:
        await update.message.reply_text("Checking your escrow wallet balance...", reply_markup=ReplyKeyboardRemove())
        balance_response = await oneshot_client.balance.get_escrow_wallet_balance()

        if balance_response and balance_response.response:
            # Assuming the response object has a 'balance' and 'decimals' attribute
            # Adjust based on the actual SDK response structure
            raw_balance = balance_response.response.balance
            decimals = balance_response.response.decimals # Or a fixed 18 for native
            
            formatted_bal = format_wei(raw_balance, decimals)
            chain_id = balance_response.response.chain_id # Assuming this is available
            network_name = oneshot_client.network # Or map chain_id to name

            await update.message.reply_text(
                f"Your escrow wallet balance on network '{network_name}' (Chain ID: {chain_id}):\n"
                f"<b>{formatted_bal}</b> native currency.",
                parse_mode=ParseMode.HTML
            )
        elif balance_response and balance_response.error:
            logger.error(f"Error fetching escrow balance: {balance_response.error.message}")
            await update.message.reply_text(f"Could not fetch escrow balance: {balance_response.error.message}")
        else:
            logger.error(f"Unexpected response from get_escrow_wallet_balance: {balance_response}")
            await update.message.reply_text("Could not fetch escrow balance due to an unexpected issue.")

    except Exception as e:
        logger.error(f"Exception fetching escrow balance: {e}", exc_info=True)
        await update.message.reply_text(f"An error occurred while fetching escrow balance: {e}")
    return ConversationHandler.END

async def prompt_token_address_for_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores token address and attempts to check its balance."""
    token_address = update.message.text
    if not token_address.startswith("0x") or len(token_address) != 42: # Basic validation
        await update.message.reply_text("Invalid address format. Please enter a valid Ethereum address (e.g., 0x...).")
        return ENTER_TOKEN_ADDRESS_FOR_BALANCE
    context.user_data['token_address_for_balance'] = token_address
    
    try:
        await update.message.reply_text(f"Checking balance for token: {token_address}...", reply_markup=ReplyKeyboardRemove())
        
        # Note: The SDK's get_balance might be for the escrow wallet's balance of a token,
        # or it might be a general balance check. This needs verification.
        # It might require a specific transaction endpoint for balanceOf if it's for an external user wallet.
        # For now, we proceed assuming it might work or provide a clear error.
        
        # Infer chain_id - replace with your actual logic if necessary
        network_name = oneshot_client.network # or os.getenv("ONESHOT_NETWORK", "sepolia")
        chain_id = get_chain_id_from_network_name(network_name)
        if not chain_id:
            await update.message.reply_text("Could not determine the chain ID for balance check. Please check bot configuration.")
            return ConversationHandler.END

        balance_response = await oneshot_client.balance.get_balance(
            chain_id=str(chain_id),
            token_address=token_address
            # user_address=update.effective_user.id # Or some other identifier if checking for the user, not escrow
        )

        if balance_response and balance_response.response:
            raw_balance = balance_response.response.balance
            decimals = balance_response.response.decimals # This is crucial for correct formatting
            formatted_bal = format_wei(raw_balance, decimals if decimals is not None else 18) # Default to 18 if no decimals
            
            # The balance returned by get_balance might be the *escrow's* balance of that token.
            # Clarify this based on SDK docs or testing.
            await update.message.reply_text(
                f"Balance for token {token_address} (possibly in escrow):\n"
                f"<b>{formatted_bal}</b> tokens (Decimals: {decimals if decimals is not None else 'assumed 18'}).",
                parse_mode=ParseMode.HTML
            )
        elif balance_response and balance_response.error:
            logger.error(f"Error fetching token balance for {token_address}: {balance_response.error.message}")
            await update.message.reply_text(
                f"Could not fetch balance for token {token_address}: {balance_response.error.message}\n"
                "This might mean the token is not recognized, or checking balance for this token requires a specific pre-configured 'balanceOf' endpoint."
            )
        else:
            logger.error(f"Unexpected response from get_balance for token {token_address}: {balance_response}")
            await update.message.reply_text(f"Could not fetch token balance for {token_address} due to an unexpected issue.")

    except Exception as e:
        logger.error(f"Exception fetching token balance for {token_address}: {e}", exc_info=True)
        await update.message.reply_text(f"An error occurred while fetching token balance: {e}")
    return ConversationHandler.END


# --- Conversation Fallbacks ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Transaction process cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

def get_transaction_handler() -> ConversationHandler:
    """Creates the ConversationHandler for transactions."""
    return ConversationHandler(
        entry_points=[CommandHandler("transaction", transaction_start)],
        states={
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_action)],
            ENTER_RECIPIENT_NATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_recipient_native)],
            ENTER_AMOUNT_NATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_amount_native)],
            CONFIRM_NATIVE_TRANSFER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_native_transfer)],
            # SELECT_BALANCE_TYPE path is handled by direct calls from select_action for now
            ENTER_TOKEN_ADDRESS_FOR_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_token_address_for_balance)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True # Tracks messages properly
    ) 