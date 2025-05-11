import logging
import os

# Configure logging
logger = logging.getLogger(__name__)

try:
    import openai
    from typing import List, Dict, Any
    
    # Configure OpenAI
    CHATGPT_API_KEY = ""
    openai.api_key = CHATGPT_API_KEY
    OPENAI_AVAILABLE = True
except ImportError:
    logger.error("OpenAI module not found. AI chat functionality will not be available.")
    OPENAI_AVAILABLE = False

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from database import get_user_expenses # Import the function to get expenses

# Define a system prompt that sets the AI's role and behavior
SYSTEM_PROMPT = """
You are Penny, a friendly financial assistant and crypto token management bot. 
Your primary goals are to:
1. Help users manage their finances through expense tracking, budgeting, and goal setting.
2. Assist with blockchain operations like checking balances, transferring tokens, and deploying new tokens.
3. Provide helpful, concise responses to questions about finances and blockchain.

When a user chats with you, you may be provided with their recent expense history. 
Feel free to comment on their spending patterns, offer insights, or suggest ways to save if it seems relevant to the conversation. 
For example, if they ask about saving money and you see high spending in a certain category, you can point that out.

Keep responses brief and to the point. If users want to use specific bot commands, tell them about:
- /expense - Track expenses
- /budget - Set budgets
- /goal - Create financial goals
- /hello - Get a financial summary
- /wallet - Check wallet balance
- /checkbalance - Check token balances
- /transaction - Manage transactions
- /tokentransfer - Transfer tokens
- /deploytoken - Deploy a new token
- /endpoints - List transaction endpoints
- /time - Check current time
- /help - Show all commands

Always be helpful, friendly, and financially-focused in your responses.
"""

# Maximum conversation history to keep per user
MAX_HISTORY_LENGTH = 10

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command messages by sending them to ChatGPT API."""
    if not OPENAI_AVAILABLE:
        await update.message.reply_text(
            "I'm sorry, but my AI capabilities are not available right now. "
            "Please use one of my commands like /hello or /help instead."
        )
        return
        
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Initialize conversation history if it doesn't exist
    if 'chat_history' not in context.user_data:
        context.user_data['chat_history'] = []

    # Fetch recent expenses for the user
    recent_expenses = get_user_expenses(user_id, limit=5) # Fetch last 5 expenses
    expense_summary = ""
    if recent_expenses:
        expense_summary = "\n\nHere are your recent expenses for context:\n"
        for expense in recent_expenses:
            # amount, category, description, date, payment_method
            expense_summary += f"- Amount: ${expense[0]:.2f}, Category: {expense[1]}, Date: {expense[3].split(' ')[0]}\n"
    
    # Add user message to history (potentially with expense summary)
    context.user_data['chat_history'].append({
        "role": "user",
        "content": user_message + expense_summary # Append expense summary to user's message
    })
    
    # Create messages array with system prompt and conversation history
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add conversation history (limited to prevent token limit issues)
    history = context.user_data['chat_history'][-MAX_HISTORY_LENGTH:]
    messages.extend(history)
    
    try:
        # Send typing action to indicate the bot is processing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Call OpenAI API
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500, # Increased max_tokens slightly to accommodate potentially longer prompts with expenses
            temperature=0.7,
            top_p=0.95
        )
        
        # Extract response text
        ai_response = response.choices[0].message.content
        
        # Add assistant response to history
        context.user_data['chat_history'].append({
            "role": "assistant",
            "content": ai_response
        })
        
        # Trim history if it gets too long
        if len(context.user_data['chat_history']) > MAX_HISTORY_LENGTH * 2:
            context.user_data['chat_history'] = context.user_data['chat_history'][-MAX_HISTORY_LENGTH * 2:]
        
        # Send response to user
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        await update.message.reply_text(
            "I'm having trouble connecting to my brain right now. Please try again later."
        )

def get_ai_chat_handler():
    """Return the handler for AI chat."""
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat) 