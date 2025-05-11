import os
from telegram import Update
from telegram.ext import ContextTypes
from database import add_user, get_user_expenses, get_user_goals, get_budget_progress

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a greeting message with user's financial summary."""
    try:
        # Get user information
        user = update.effective_user
        user_id = user.id
        username = user.username

        # Add user to database
        add_user(user_id, username)

        # Get user's recent expenses
        expenses = get_user_expenses(user_id, limit=3)
        
        # Get user's active goals
        goals = get_user_goals(user_id)
        
        # Get user's budget progress
        budget_progress = get_budget_progress(user_id)
        
        # Build the message
        text = f"👋 Hi {user.first_name}! I'm Penny, your personal financial assistant!\n\n"
        text += f"Your user ID: {user_id}\n"
        text += f"Username: @{username if username else 'Not set'}\n\n"
        
        # Add budget summary if available
        if budget_progress:
            total_budget, total_spent = budget_progress
            if total_budget:
                remaining = total_budget - total_spent
                progress = (total_spent / total_budget) * 100
                text += "💰 Budget Summary:\n"
                text += f"• Total Budget: ${total_budget:.2f}\n"
                text += f"• Spent: ${total_spent:.2f} ({progress:.1f}%)\n"
                text += f"• Remaining: ${remaining:.2f}\n\n"
        
        # Add recent expenses if available
        if expenses:
            text += "📊 Your recent expenses:\n"
            for amount, category, description, date, payment_method in expenses:
                text += f"• ${amount:.2f} - {category}"
                if description:
                    text += f" ({description})"
                text += f"\n"
            text += "\n"
        
        # Add goals summary if available
        if goals:
            text += "🎯 Active Goals:\n"
            for _, name, target, current, _, _, _ in goals:
                progress = (current / target) * 100 if target > 0 else 0
                text += f"• {name}: ${current:.2f}/${target:.2f} ({progress:.1f}%)\n"
            text += "\n"
        
        text += "I can help you with:\n"
        text += "• Tracking your expenses (/expense)\n"
        text += "• Setting budgets (/budget)\n"
        text += "• Viewing spending reports (/report)\n"
        text += "• Setting financial goals (/goal)\n"
        text += "• Checking your wallet balance (/wallet)\n"
        text += "• Managing transactions (/transaction)\n"
        text += "• Checking token balances (/checkbalance)\n"
        text += "• Deploying your own token (/deploytoken)\n"
        text += "• Listing transaction endpoints (/endpoints)\n"
        text += "• Transferring tokens (/tokentransfer)\n"
        text += "• Showing escrow wallet info (/myescrowinfo)\n"
        text += "• Checking current time (/time)\n\n"
        text += "Just let me know what you need help with! 💰"

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text("❌ An error occurred while processing your request.")
        print(f"hello error: {e}") 