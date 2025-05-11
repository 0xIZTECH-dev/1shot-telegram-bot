import logging
import re

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler
)
from telegram.constants import ParseMode

from oneshot import (
    oneshot_client,
    BUSINESS_ID
)

from helpers import (
    canceler, 
    convert_to_wei
)
from objects import (
    TransactionMemo,
    TxType,
    ConversationState
)

logger = logging.getLogger(__name__)

# Define states for the token transfer conversation
class TokenTransferState:
    SELECT_TOKEN = 20
    ENTER_RECIPIENT = 21
    ENTER_AMOUNT = 22
    CONFIRM_TRANSFER = 23

async def token_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the token transfer process."""
    try:
        # Clear any previous data
        if 'token_transfer' in context.user_data:
            context.user_data.pop('token_transfer')
        
        # Initialize token transfer data
        context.user_data['token_transfer'] = {}
        
        # Get deployed tokens for the user
        await update.message.reply_text(
            "🔍 Fetching your deployed tokens...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # List transaction endpoints to find the token deployer
        transaction_endpoints = await oneshot_client.transactions.list(
            business_id=BUSINESS_ID,
            params={"chain_id": "11155111", "name": "1Shot Demo Sepolia Token Deployer"}
        )
        
        if not transaction_endpoints.response:
            await update.message.reply_text(
                "❌ Token deployment endpoint not found. Please contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Get wallet to check for deployed tokens
        wallets = await oneshot_client.wallets.list(
            BUSINESS_ID,
            {"chain_id": "11155111"}  # Sepolia testnet
        )
        
        if not wallets.response:
            await update.message.reply_text(
                "❌ No escrow wallet found. Please contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # For demo purposes, we'll ask the user to enter the token address manually
        # In a production system, you would query the blockchain or your database
        # to get tokens deployed by this user
        
        message = (
            "🔄 *Token Transfer*\n\n"
            "Let's transfer some tokens! Please provide the following information:\n\n"
            "Enter the address of the token you want to transfer:"
        )
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return TokenTransferState.SELECT_TOKEN
        
    except Exception as e:
        logger.error(f"Error in token_transfer: {e}")
        await update.message.reply_text(
            "❌ An error occurred while starting token transfer.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def select_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the token address and ask for the recipient address."""
    try:
        token_address = update.message.text.strip()
        
        # Validate Ethereum address format
        if not re.match(r'^0x[a-fA-F0-9]{40}$', token_address):
            await update.message.reply_text(
                "❌ Invalid Ethereum address format. Please enter a valid token address:",
                parse_mode=ParseMode.MARKDOWN
            )
            return TokenTransferState.SELECT_TOKEN
        
        # Store the token address
        context.user_data['token_transfer']['token_address'] = token_address
        
        await update.message.reply_text(
            "Great! Now enter the recipient address (where you want to send the tokens):",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return TokenTransferState.ENTER_RECIPIENT
        
    except Exception as e:
        logger.error(f"Error in select_token: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return TokenTransferState.SELECT_TOKEN

async def enter_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the recipient address and ask for the amount."""
    try:
        recipient_address = update.message.text.strip()
        
        # Validate Ethereum address format
        if not re.match(r'^0x[a-fA-F0-9]{40}$', recipient_address):
            await update.message.reply_text(
                "❌ Invalid Ethereum address format. Please enter a valid recipient address:",
                parse_mode=ParseMode.MARKDOWN
            )
            return TokenTransferState.ENTER_RECIPIENT
        
        # Store the recipient address
        context.user_data['token_transfer']['recipient_address'] = recipient_address
        
        await update.message.reply_text(
            "How many tokens would you like to transfer? (Enter a positive number):",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return TokenTransferState.ENTER_AMOUNT
        
    except Exception as e:
        logger.error(f"Error in enter_recipient: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return TokenTransferState.ENTER_RECIPIENT

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the amount and ask for confirmation."""
    try:
        amount_text = update.message.text.strip()
        
        # Validate the amount
        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid positive number:",
                parse_mode=ParseMode.MARKDOWN
            )
            return TokenTransferState.ENTER_AMOUNT
        
        # Store the amount
        context.user_data['token_transfer']['amount'] = amount
        
        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("Confirm ✅", callback_data="confirm"),
                InlineKeyboardButton("Cancel ❌", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Format confirmation message
        token_address = context.user_data['token_transfer']['token_address']
        recipient = context.user_data['token_transfer']['recipient_address']
        
        message = (
            "🔍 *Transfer Summary*\n\n"
            f"*Token Address:* `{token_address}`\n"
            f"*Recipient:* `{recipient}`\n"
            f"*Amount:* {amount} tokens\n\n"
            "Please confirm this transfer:"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return TokenTransferState.CONFIRM_TRANSFER
        
    except Exception as e:
        logger.error(f"Error in enter_amount: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return TokenTransferState.ENTER_AMOUNT

async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the token transfer transaction."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text(
            "Token transfer cancelled.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    try:
        # Get transaction parameters
        token_address = context.user_data['token_transfer']['token_address']
        recipient = context.user_data['token_transfer']['recipient_address']
        amount = context.user_data['token_transfer']['amount']
        
        # Get wallets and transaction endpoints
        wallets = await oneshot_client.wallets.list(
            BUSINESS_ID,
            {"chain_id": "11155111"}
        )
        
        if not wallets.response:
            await query.edit_message_text(
                "❌ No escrow wallet found. Please contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Create a transaction endpoint for the token transfer if it doesn't exist
        transaction_endpoints = await oneshot_client.transactions.list(
            business_id=BUSINESS_ID,
            params={"chain_id": "11155111", "contract_address": token_address, "function_name": "transfer"}
        )
        
        # If no transfer endpoint exists for this token, create one
        if not transaction_endpoints.response:
            await query.edit_message_text(
                "⏳ Setting up token transfer endpoint...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Create a new transaction endpoint for token transfers
            endpoint_payload = {
                "chain": "11155111",  # Sepolia testnet
                "contractAddress": token_address,
                "escrowWalletId": wallets.response[0].id,
                "name": f"Token Transfer for {token_address[:6]}...{token_address[-4:]}",
                "description": "ERC20 token transfer on Sepolia testnet",
                "functionName": "transfer",
                "stateMutability": "nonpayable",
                "inputs": [
                    {
                        "name": "to",
                        "type": "address",
                        "index": 0
                    },
                    {
                        "name": "amount",
                        "type": "uint256",
                        "index": 1
                    }
                ],
                "outputs": []
            }
            
            new_endpoint = await oneshot_client.transactions.create(
                business_id=BUSINESS_ID,
                params=endpoint_payload
            )
            
            transaction_id = new_endpoint.id
        else:
            transaction_id = transaction_endpoints.response[0].id
        
        # Create transaction memo
        memo = TransactionMemo(
            tx_type=TxType.TOKENS_TRANSFERRED.value,
            associated_user_id=update.effective_user.id,
            note_to_user=f"Transfer of {amount} tokens to {recipient}"
        )
        
        # Execute the transaction
        token_decimals = 18  # Standard ERC20 decimals, adjust if needed
        wei_amount = convert_to_wei(str(amount), decimals=token_decimals)
        
        execution = await oneshot_client.transactions.execute(
            transaction_id=transaction_id,
            params={
                "to": recipient,
                "amount": wei_amount
            },
            memo=memo.model_dump_json()
        )
        
        logger.info(f"Token transfer transaction executed: {execution.id}")
        
        await query.edit_message_text(
            "✅ Token transfer initiated! You will be notified once the transaction is confirmed.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in confirm_transfer: {e}")
        await query.edit_message_text(
            f"❌ An error occurred while processing your token transfer: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def token_transfer_success(execution_id: str, memo: TransactionMemo, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify the user that their token transfer has succeeded."""
    try:
        success_message = (
            "🎉 *Token Transfer Successful!*\n\n"
            f"{memo.note_to_user}\n\n"
            f"Transaction ID: `{execution_id}`\n"
            f"View on [Etherscan](https://sepolia.etherscan.io/tx/{execution_id})"
        )
        
        await context.bot.send_message(
            chat_id=memo.associated_user_id,
            text=success_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in token_transfer_success: {e}")
        await context.bot.send_message(
            chat_id=memo.associated_user_id,
            text="❌ An error occurred while processing your token transfer notification.",
            parse_mode=ParseMode.MARKDOWN
        )

def get_token_transfer_handler():
    """Return the conversation handler for token transfers."""
    return ConversationHandler(
        entry_points=[CommandHandler("tokentransfer", token_transfer)],
        states={
            TokenTransferState.SELECT_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_token)
            ],
            TokenTransferState.ENTER_RECIPIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_recipient)
            ],
            TokenTransferState.ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)
            ],
            TokenTransferState.CONFIRM_TRANSFER: [
                CallbackQueryHandler(confirm_transfer, pattern="^(confirm|cancel)$")
            ]
        },
        fallbacks=[CommandHandler("cancel", canceler)],
        per_chat=True,
        per_message=True
    )
