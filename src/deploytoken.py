import os
import logging

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
from telegram.helpers import mention_html

logger = logging.getLogger(__name__)

from oneshot import (
    oneshot_client,
    BUSINESS_ID
)

from helpers import (
    is_nonnegative_integer, 
    canceler, 
    convert_to_wei
)
from objects import (
    TransactionMemo,
    TxType,
    TokenInfo,
    ConversationState, 
)

async def deploy_token_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the token deployment conversation when /deploytoken is called."""
    # Clear any previous data
    if 'name' in context.user_data: context.user_data.pop('name')
    if 'ticker' in context.user_data: context.user_data.pop('ticker')
    if 'description' in context.user_data: context.user_data.pop('description')
    if 'image' in context.user_data: context.user_data.pop('image')

    await update.message.reply_text(
        "Let's deploy a new token! What do you want to name your token?",
        parse_mode=ParseMode.MARKDOWN
        )
    return ConversationState.TOKEN_NAMING

async def get_naming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store token name and ask for the token ticker (symbol)."""
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text(
            "❌ Token name must be at least 3 characters long. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationState.TOKEN_NAMING
    context.user_data["name"] = name
    await update.message.reply_text("Great! What do you want the token symbol to be? (e.g., BTC, ETH)")
    return ConversationState.TOKEN_TICKER

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the token ticker and ask for a description."""
    ticker = update.message.text.strip().upper()
    if not (2 <= len(ticker) <= 5):
        await update.message.reply_text(
            "❌ Token symbol must be between 2 and 5 characters. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationState.TOKEN_TICKER
    context.user_data["ticker"] = ticker
    await update.message.reply_text("Please provide a short description for your token:")
    return ConversationState.TOKEN_DESCRIPTION

async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the description and ask the user to upload an image."""
    description = update.message.text.strip()
    if len(description) < 10:
        await update.message.reply_text(
            "❌ Description must be at least 10 characters long. Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationState.TOKEN_DESCRIPTION
    context.user_data["description"] = description
    await update.message.reply_text("Great! Please upload an image for the token (e.g., its logo). This is optional, you can type /skip to omit it.")
    return ConversationState.TOKEN_IMAGE

async def get_premint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the image (if provided) and ask for how many tokens to premint."""
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data["image"] = file_id
        await update.message.reply_text(
            "Awesome! How many tokens should be minted to your admin address (must be a non-negative integer)?"
        )
    elif update.message.text and update.message.text.lower() == '/skip':
        context.user_data["image"] = None # Explicitly set to None if skipped
        await update.message.reply_text(
            "No image it is! How many tokens should be minted to your admin address (must be a non-negative integer)?"
        )
    else:
        await update.message.reply_text("❌ Please upload a valid image or type /skip.")
        return ConversationState.TOKEN_IMAGE
    return ConversationState.TOKEN_PREMINT

async def skip_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles skipping the image upload."""
    context.user_data["image"] = None
    await update.message.reply_text(
        "No image it is! How many tokens should be minted to your admin address (must be a non-negative integer)?"
    )
    return ConversationState.TOKEN_PREMINT

async def finalize_token_deployment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the premint amount, make the API call, and end the conversation."""
    premint = update.message.text.strip()
    if not is_nonnegative_integer(premint):
        await update.message.reply_text(
            "❌ Invalid input! Please enter a positive integer for the premint amount (e.g., 1000000)."
        )
        return ConversationState.TOKEN_PREMINT

    try:
        await update.message.reply_text("🚀 Processing your token deployment... this might take a moment.")

        chain_id = '11155111' # Sepolia testnet
        name = context.user_data["name"]
        ticker = context.user_data["ticker"]
        description = context.user_data["description"]
        image_file_id = context.user_data.get("image")

        wallets = await oneshot_client.wallets.list(BUSINESS_ID, {"chain_id": chain_id})
        if not wallets.response:
            await update.message.reply_text("❌ Error: No escrow wallet found on Sepolia. Please contact support.")
            return ConversationHandler.END
        admin_address = wallets.response[0].account_address

        transaction_endpoint_list = await oneshot_client.transactions.list(
            business_id=BUSINESS_ID,
            params={"chain_id": chain_id, "name": "1Shot Demo Sepolia Token Deployer"}
        )
        if not transaction_endpoint_list.response:
            await update.message.reply_text("❌ Error: Token deployment endpoint not found. Please contact support.")
            return ConversationHandler.END
        transaction_endpoint_id = transaction_endpoint_list.response[0].id

        token_info = TokenInfo(
            name=name,
            ticker=ticker,
            description=description,
            image_file_id=image_file_id if image_file_id else "" # Ensure it's a string
        )
        memo = TransactionMemo(
            tx_type=TxType.TOKEN_CREATION.value,
            associated_user_id=update.effective_user.id,
            note_to_user=token_info.model_dump_json()
        )

        execution = await oneshot_client.transactions.execute(
            transaction_id=transaction_endpoint_id,
            params={
                "name": name,
                "ticker": ticker,
                "admin": admin_address,
                "premint": convert_to_wei(premint),
            },
            memo=memo.model_dump_json()
        )
        logger.info(f"Token creation transaction executed: {execution.id} by user {update.effective_user.id}")

        await update.message.reply_text(
            "✅ Your token is being deployed! You will be notified once it's ready."
        )

    except Exception as e:
        logger.error(f"Error in finalize_token_deployment for user {update.effective_user.id}: {e}")
        await update.message.reply_text(
            "❌ An unexpected error occurred while deploying your token. Please try again later or contact support."
        )
    
    # Clean up user_data for this conversation
    for key in ["name", "ticker", "description", "image"]:
        if key in context.user_data: context.user_data.pop(key)
    
    return ConversationHandler.END

async def successful_token_deployment(token_address: str, memo: TransactionMemo, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify the user that their token has been created."""
    token_info = TokenInfo.model_validate_json(memo.note_to_user)

    success_message = (
        f"🎉 <b>New Token Deployed!</b> 🎉\n\n"
        f"<b>Name:</b> {token_info.name}\n"
        f"<b>Symbol:</b> {token_info.ticker}\n"
        f"<b>Description:</b> {token_info.description}\n"
        f"<b>Address:</b> <a href='https://sepolia.etherscan.io/token/{token_address}'>{token_address}</a>\n"
    )
    
    # Send message with photo if available, otherwise just text
    if token_info.image_file_id:
        try:
            await context.bot.send_photo(
                chat_id=memo.associated_user_id, 
                photo=token_info.image_file_id, 
                caption=success_message, 
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error sending photo for token deployment for user {memo.associated_user_id}: {e}. Sending text message instead.")
            await context.bot.send_message(
                chat_id=memo.associated_user_id, 
                text=success_message, 
                parse_mode=ParseMode.HTML
            )
    else:
        await context.bot.send_message(
            chat_id=memo.associated_user_id, 
            text=success_message, 
            parse_mode=ParseMode.HTML
        )

def get_token_deployment_conversation_handler() -> ConversationHandler:
    """Create and return the conversation handler for token deployment."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("deploytoken", deploy_token_command)
            ],
        states={
            ConversationState.TOKEN_NAMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_naming)],
            ConversationState.TOKEN_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            ConversationState.TOKEN_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_image)],
            ConversationState.TOKEN_IMAGE: [
                MessageHandler(filters.PHOTO & ~filters.COMMAND, get_premint),
                CommandHandler("skip", skip_image) # Allow skipping image with /skip
                ],
            ConversationState.TOKEN_PREMINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_token_deployment)],
        },
        fallbacks=[CommandHandler("cancel", canceler)],
        per_chat=True, # Ensures user_data is per chat
        per_message=False # Set to False according to docs for multi-message conversations to work as expected for user_data
    )
