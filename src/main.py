#!/usr/bin/env python
import os
import logging
from http import HTTPStatus
from contextlib import asynccontextmanager
from checkbalance import check_balance
from checktime import get_time
from hello import hello
from wallet import get_wallet_handler
from transaction import get_transaction_handler
from transactionendpoints import get_transaction_endpoints_handler
from report import get_report_handler
from escrowinfo import get_escrow_info_handler


# useful object patterns for a Telegram bot that interacts with the 1Shot API
from objects import (
    TransactionMemo,
    TxType,
    ConversationState
)

# the file contains various helper functions for the bot
from helpers import (
    canceler,
    get_token_deployer_endpoint_creation_payload
)

# this file shows how you can track what chats your bot has been added to
from chattracker import track_chats

# this file shows how you can implement a non-trivial conversation flow that deployes and ERC20 token
from deploytoken import (
    get_token_deployment_conversation_handler,
    successful_token_deployment
)

# Auth against 1Shot API is done in oneshot.py where we implement a singleton pattern
from oneshot import (
    oneshot_client, # the 1Shot API async client that we instantiated in oneshot.py
    BUSINESS_ID, # The organization id for your 1Shot API account
    log_token
)

# the 1Shot Python SDK implements a helpful Pydantic dataclass model for Webhook callback payloads
from uxly_1shot_client import WebhookPayload, verify_webhook

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ChatMemberHandler,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    TypeHandler,
)
from telegram.constants import ParseMode

import uvicorn
from database import add_user
from expense import get_expense_conversation_handler
from goal import get_goal_conversation_handler
from budget import get_budget_conversation_handler
from tokentransfer import get_token_transfer_handler, token_transfer_success
from aichat import get_ai_chat_handler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

URL = os.getenv("TUNNEL_BASE_URL") # this is the base url where Telegram will send update callbacks to
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Get this token from @BotFather
PORT = 8000 # The port that uvicorn will attach to

# This is an entrypoint handler for the example bot, it gets triggered when a user types /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot and show the main menu."""
    # Register user in database
    user = update.effective_user
    add_user(user.id, user.username)

    text = f"👋 Hi {user.first_name}! I'm Penny, your personal financial assistant!\n\n"
    text += "I can help you withhhh:\n"
    text += "• Tracking your expenses (/expense)\n"
    text += "• Setting budgets (/budget)\n"
    text += "• Viewing spending reports (/report)\n"
    text += "• Setting financial goals (/goal)\n"
    text += "• Getting spending insights (/insights)\n"
    text += "• Deploy your own token (/deploytoken)\n"
    text += "• Transferring tokens (/tokentransfer)\n\n"
    text += "Just let me know what you need help with! 💰"

    # If we're starting over we don't need to send a new message
    if context.user_data.get(ConversationState.START_OVER):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)

    context.user_data[ConversationState.START_OVER] = False
    return ConversationState.START_ROUTES

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays help information."""
    help_text = (
        "🤖 *Penny Bot Commands* 🤖\n\n"
        "Here are all the commands you can use:\n\n"
        "📊 *Finance Management*\n"
        "• /expense - Track your expenses\n"
        "• /budget - Set and manage budgets\n"
        "• /goal - Create financial goals\n"
        "• /report - View spending reports\n\n"
        "💰 *Blockchain & Tokens*\n"
        "• /wallet - Check wallet balance\n"
        "• /checkbalance - Check token balances\n"
        "• /transaction - Manage transactions\n"
        "• /tokentransfer - Transfer tokens\n"
        "• /deploytoken - Deploy a new token\n"
        "• /endpoints - List transaction endpoints\n"
        "• /myescrowinfo - Show your escrow wallet details\n\n"
        "ℹ️ *General*\n"
        "• /hello - Get a financial summary\n"
        "• /time - Check current time\n"
        "• /help - Show this help message\n\n"
        "You can also chat with me naturally about finances and blockchain topics!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# This handles webhooks coming from 1Shot API
async def webhook_update(update: WebhookPayload, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming webhook updates."""
    # Extract the payload from the update
    event_type = update.event_name

    if event_type == "TransactionExecutionSuccess":
        # check for the Transaction Memo, if its not set, we don't know what to do with it
        if not update.data.transaction_execution_memo:
            logger.error(f"TransactionMemo is null: {update.data.transaction_execution_id}")
            return
        
        tx_memo = TransactionMemo.model_validate_json(update.data.transaction_execution_memo)
        chat_id = tx_memo.chat_id # Assuming chat_id is part of your TransactionMemo

        # Check what kind of transaction was executed based on the memo and handle appropriately for you application
        if tx_memo.tx_type == TxType.TOKEN_CREATION:
            token_address = None
            for log in update.data.logs:
                if log.name == "TokenCreated":
                    token_address = log.args[0]
            await successful_token_deployment(token_address, tx_memo, context)
        elif tx_memo.tx_type == TxType.TOKENS_TRANSFERRED:
            transaction_hash = update.data.transaction_receipt.hash
            await token_transfer_success(transaction_hash, tx_memo, context)
        elif tx_memo.tx_type == TxType.NATIVE_CURRENCY_TRANSFER:
            transaction_hash = update.data.transaction_receipt.hash
            amount_readable = tx_memo.amount_readable if hasattr(tx_memo, 'amount_readable') and tx_memo.amount_readable else "an amount of"
            recipient_address = tx_memo.recipient_address if hasattr(tx_memo, 'recipient_address') and tx_memo.recipient_address else "the recipient"
            if chat_id:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Native currency transfer successful!\nTransfer of {amount_readable} native currency to {recipient_address} confirmed.\nTransaction Hash: `{transaction_hash}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            logger.info(f"Native currency transfer successful. Hash: {transaction_hash}, Memo: {tx_memo}")
        else:
            # implement other transaction types as needed
            logger.error(f"Unknown transaction type: {tx_memo.tx_type}")

# lifespane is used by FastAPI on startup and shutdown: https://fastapi.tiangolo.com/advanced/events/
# When the server is shutting down, the code after "yield" will be executed when shutting down
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize and shutdown the Telegram bot."""
    app.application = (
        Application.builder().token(TOKEN).updater(None).build()
    )

    # lets start by checking that we have an escrow wallet provisioned for our account on the Sepolia network
    # if not we will exit since we must have one to continue
    wallets = await oneshot_client.wallets.list(BUSINESS_ID, {"chain_id": "11155111"})
    if (len(wallets.response) != 1) and (float(wallets.response[0].account_balance_details.balance) > 0.0001):
        raise RuntimeError(
            "Escrow wallet not provisioned or insufficient balance on the Sepolia network. "
            "Please ensure an escrow wallet exists and has sufficient funds by logging into https://app.1shotapi.dev/escrow-wallets."
        )
    else:
        logger.info("Escrow wallet is provisioned and has sufficient funds.")

    # Add this after the escrow wallet check but before the yield
    await log_token()  # This will log the token

    # to keep this demo self contained, we are going to check our 1Shot API account for an existing transaction endpoint for the 
    # contract at 0xA1BfEd6c6F1C3A516590edDAc7A8e359C2189A61 on the Sepolia network, if we don't have one, we'll create it automatically
    # then we'll use that endpoint in the conversation flow to deploy tokens from a Telegram conversation
    # for a more serious application you will probably create your required contract function endpionts ahead of time
    # and input their transaction ids as environment variables
    transaction_endpoints = await oneshot_client.transactions.list(
        business_id=BUSINESS_ID,
        params={"chain_id": "11155111", "name": "1Shot Demo Sepolia Token Deployer"}
    )
    if len(transaction_endpoints.response) == 0:
        logger.info("Creating new transaction endpoint for token deployer contract.")
        deployer_endpoint_payload = get_token_deployer_endpoint_creation_payload(
            chain_id="11155111",
            contract_address="0xA1BfEd6c6F1C3A516590edDAc7A8e359C2189A61",
            escrow_wallet_id=wallets.response[0].id
        )
        new_transaction_endpoint = await oneshot_client.transactions.create(
            business_id=BUSINESS_ID,
            params=deployer_endpoint_payload
        )
    else:
        logger.info(f"Transaction endpoint already exists, skipping creation.")
        
    # Here is where we register the functionality of our Telegram bot, starting with a ConversationHandler
    # You can nest conversation flows inside each other for more complex applications: https://docs.python-telegram-bot.org/en/stable/examples.nestedconversationbot.html
    entrypoint_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ConversationState.START_ROUTES: [
                CommandHandler("start", start),
                CallbackQueryHandler(start, pattern="^start$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", canceler)
        ],
        per_chat=True,
        per_message=True
    )

    # handle when the user calls /start
    app.application.add_handler(entrypoint_handler)

    app.application.add_handler(CommandHandler("checkbalance", check_balance))
    app.application.add_handler(CommandHandler("time", get_time))
    app.application.add_handler(CommandHandler("hello", hello))
    app.application.add_handler(CommandHandler("help", help_command))
    app.application.add_handler(get_wallet_handler())
    app.application.add_handler(get_transaction_handler())
    app.application.add_handler(get_transaction_endpoints_handler())
    app.application.add_handler(get_expense_conversation_handler())
    app.application.add_handler(get_goal_conversation_handler())
    app.application.add_handler(get_budget_conversation_handler())
    app.application.add_handler(get_token_deployment_conversation_handler())
    app.application.add_handler(get_token_transfer_handler())
    app.application.add_handler(get_report_handler())
    app.application.add_handler(get_escrow_info_handler())
    # handles updates from 1shot by selecting Telegram updates of type WebhookPayload
    app.application.add_handler(TypeHandler(type=WebhookPayload, callback=webhook_update))

    # track what chats the bot is in, can be useful for group-based features
    app.application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # Add AI chat handler to respond to non-command messages
    # This should be added last so it doesn't interfere with other handlers
    app.application.add_handler(get_ai_chat_handler())

    # TODO: use secret-token: https://docs.python-telegram-bot.org/en/stable/telegram.bot.html#telegram.Bot.set_webhook.params.secret_token
    await app.application.bot.set_webhook(url=f"{URL}/telegram", allowed_updates=Update.ALL_TYPES)
    await app.application.initialize()
    await app.application.start()

    yield
    await app.application.stop()

# FastAPI app
app = FastAPI(lifespan=lifespan)

# This route is for Telegram to send Updates to the bot about message and interactions from users
# Its more efficient that using long polling
@app.post("/telegram")
async def telegram(request: Request):
    data = await request.json()
    update = Update.de_json(data, app.application.bot)
    await app.application.update_queue.put(update)
    return Response(status_code=HTTPStatus.OK)

# This route is for 1shot to send updates to the bot about transactions that the bot initiated
@app.api_route("/1shot", methods=["POST"])
async def oneshot_updates(request: Request):
    try:
        body = await request.json()
        webhook_payload = WebhookPayload(**body)

        # we'll now authenticate the callback to make sure it came from 1Shot API
        # we need to look up the public key of our endpoint (each endpoint creates has its own public key) 
        # this will be slow in production, so if you have a lot of users making transactions, a better 
        # strategy would be to store the public keys in your bot's database for faster access
        # more info on 1Shot Webhooks here: https://docs.1shotapi.com/transactions.html#webhooks
        transaction_endpoints = await oneshot_client.transactions.list(
            business_id=BUSINESS_ID,
            params={"chain_id": "11155111", "name": "1Shot Demo Sepolia Token Deployer"}
        )
        webhook_public_key = transaction_endpoints.response[0].public_key

        signature = body.pop("signature", None)

        if not signature or not webhook_public_key:
            raise HTTPException(status_code=400, detail="Signature or public key missing")
        
        is_valid = verify_webhook(
            body=body,
            signature=signature,
            public_key=webhook_public_key
        )

        if not is_valid:
            raise HTTPException(status_code=403, detail="Invalid signature")

        # we put objects of type WebhookPayload into the update queue
        # Updates will trigger the webhook_update handler via the TypeHandler registered on startup
        await app.application.update_queue.put(webhook_payload)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Error processing 1Shot webhook: {e}")
        return Response(status_code=HTTPStatus.NOT_ACCEPTABLE)

# This is a simple healthcheck endpoint to verify that the bot is running
@app.get("/healthcheck")
async def health():
    return PlainTextResponse("The bot is still running fine :)", status_code=HTTPStatus.OK)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
