from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from database import add_budget, get_user_budgets, update_budget, delete_budget, get_user_categories
from objects import ConversationState
from datetime import datetime, timedelta

# States for the budget conversation
BUDGET_CATEGORY, BUDGET_AMOUNT, BUDGET_PERIOD = range(3)

async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the budget tracking conversation."""
    # Get user's budgets
    budgets = get_user_budgets(update.effective_user.id)
    
    if budgets:
        # Show existing budgets
        text = "💰 Your current budgets:\n\n"
        for budget_id, category, amount, period, start_date, end_date in budgets:
            text += f"• {category}\n"
            text += f"  Amount: ${amount:.2f}\n"
            text += f"  Period: {period}\n"
            if start_date and end_date:
                text += f"  Valid: {start_date} to {end_date}\n"
            text += "\n"
        
        # Add buttons for actions
        keyboard = [
            [InlineKeyboardButton("➕ New Budget", callback_data="new_budget")],
            [InlineKeyboardButton("📊 Update Budget", callback_data="update_budget")],
            [InlineKeyboardButton("❌ Delete Budget", callback_data="delete_budget")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        # No budgets yet, start creating one
        await update.message.reply_text(
            "💰 Let's set up your first budget!\n\n"
            "What category would you like to budget for? (e.g., Food, Transportation, Entertainment)"
        )
        return BUDGET_CATEGORY
    
    return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button callbacks for budget actions."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_budget":
        await query.edit_message_text(
            "💰 Let's set up a new budget!\n\n"
            "What category would you like to budget for? (e.g., Food, Transportation, Entertainment)"
        )
        return BUDGET_CATEGORY
    
    elif query.data == "update_budget":
        budgets = get_user_budgets(update.effective_user.id)
        if not budgets:
            await query.edit_message_text("You don't have any budgets to update.")
            return ConversationHandler.END
        
        keyboard = []
        for budget_id, category, amount, period, _, _ in budgets:
            keyboard.append([InlineKeyboardButton(
                f"{category} (${amount:.2f} - {period})",
                callback_data=f"update_{budget_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Select a budget to update:",
            reply_markup=reply_markup
        )
        return BUDGET_CATEGORY
    
    elif query.data == "delete_budget":
        budgets = get_user_budgets(update.effective_user.id)
        if not budgets:
            await query.edit_message_text("You don't have any budgets to delete.")
            return ConversationHandler.END
        
        keyboard = []
        for budget_id, category, amount, period, _, _ in budgets:
            keyboard.append([InlineKeyboardButton(
                f"{category} (${amount:.2f} - {period})",
                callback_data=f"delete_{budget_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Select a budget to delete:",
            reply_markup=reply_markup
        )
        return BUDGET_CATEGORY
    
    elif query.data.startswith("update_"):
        budget_id = int(query.data.split("_")[1])
        context.user_data['update_budget_id'] = budget_id
        await query.edit_message_text(
            "Enter the new budget amount:"
        )
        return BUDGET_AMOUNT
    
    elif query.data.startswith("delete_"):
        budget_id = int(query.data.split("_")[1])
        delete_budget(budget_id)
        await query.edit_message_text("🗑️ Budget deleted successfully!")
        return ConversationHandler.END
    
    return ConversationHandler.END

async def budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the budget category."""
    if update.callback_query:
        # Handle budget update amount
        try:
            amount = float(update.callback_query.message.text)
            budget_id = context.user_data.get('update_budget_id')
            if budget_id:
                update_budget(budget_id, amount)
                await update.callback_query.edit_message_text(
                    f"✅ Budget updated to ${amount:.2f}!"
                )
                return ConversationHandler.END
        except ValueError:
            await update.callback_query.edit_message_text(
                "❌ Please enter a valid number."
            )
            return BUDGET_AMOUNT
    else:
        context.user_data['budget_category'] = update.message.text
        await update.message.reply_text(
            "💰 What's your budget amount? (e.g., 500.00):"
        )
        return BUDGET_AMOUNT

async def budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the budget amount."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Please enter a positive amount.")
            return BUDGET_AMOUNT
        
        context.user_data['budget_amount'] = amount
        
        keyboard = [
            [InlineKeyboardButton("Daily", callback_data="period_daily")],
            [InlineKeyboardButton("Weekly", callback_data="period_weekly")],
            [InlineKeyboardButton("Monthly", callback_data="period_monthly")],
            [InlineKeyboardButton("Yearly", callback_data="period_yearly")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📅 Select the budget period:",
            reply_markup=reply_markup
        )
        return BUDGET_PERIOD
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return BUDGET_AMOUNT

async def budget_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the budget period and save the budget."""
    query = update.callback_query
    await query.answer()
    
    period = query.data.split("_")[1]
    
    # Store data before clearing
    budget_category = context.user_data['budget_category']
    budget_amount = context.user_data['budget_amount']
    
    # Calculate start and end dates based on period
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = None
    
    if period == "daily":
        end_date = start_date
    elif period == "weekly":
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        # Add one month
        current = datetime.now()
        if current.month == 12:
            end_date = datetime(current.year + 1, 1, current.day).strftime("%Y-%m-%d")
        else:
            end_date = datetime(current.year, current.month + 1, current.day).strftime("%Y-%m-%d")
    elif period == "yearly":
        end_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    
    # Add budget to database
    add_budget(
        user_id=update.effective_user.id,
        category=budget_category,
        amount=budget_amount,
        period=period,
        start_date=start_date,
        end_date=end_date
    )
    
    # Clear user data
    context.user_data.clear()
    
    await query.edit_message_text(
        "✅ Budget created successfully!\n\n"
        f"Category: {budget_category}\n"
        f"Amount: ${budget_amount:.2f}\n"
        f"Period: {period.capitalize()}\n"
        f"Valid until: {end_date}"
    )
    return ConversationHandler.END

async def cancel_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the budget creation conversation."""
    context.user_data.clear()
    await update.message.reply_text("❌ Budget creation cancelled.")
    return ConversationHandler.END

def get_budget_conversation_handler() -> ConversationHandler:
    """Get the budget conversation handler."""
    return ConversationHandler(
        entry_points=[CommandHandler("budget", budget)],
        states={
            BUDGET_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, budget_category),
                CallbackQueryHandler(button_callback)
            ],
            BUDGET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, budget_amount),
                CallbackQueryHandler(button_callback)
            ],
            BUDGET_PERIOD: [
                CallbackQueryHandler(budget_period)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_budget)]
    ) 