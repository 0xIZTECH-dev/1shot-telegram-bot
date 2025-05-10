from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from database import add_goal, get_user_goals, update_goal_progress, complete_goal, delete_goal
from objects import ConversationState
from datetime import datetime

# States for the goal conversation
GOAL_NAME, GOAL_AMOUNT, GOAL_DEADLINE, GOAL_CATEGORY = range(4)

async def goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the goal tracking conversation."""
    # Get user's active goals
    goals = get_user_goals(update.effective_user.id)
    
    if goals:
        # Show existing goals
        text = "🎯 Your current financial goals:\n\n"
        for goal_id, name, target, current, deadline, category, status in goals:
            progress = (current / target) * 100 if target > 0 else 0
            text += f"• {name}\n"
            text += f"  Target: ${target:.2f}\n"
            text += f"  Current: ${current:.2f} ({progress:.1f}%)\n"
            if deadline:
                text += f"  Deadline: {deadline}\n"
            if category:
                text += f"  Category: {category}\n"
            text += "\n"
        
        # Add buttons for actions
        keyboard = [
            [InlineKeyboardButton("➕ New Goal", callback_data="new_goal")],
            [InlineKeyboardButton("📊 Update Progress", callback_data="update_progress")],
            [InlineKeyboardButton("✅ Complete Goal", callback_data="complete_goal")],
            [InlineKeyboardButton("❌ Delete Goal", callback_data="delete_goal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        # No goals yet, start creating one
        await update.message.reply_text(
            "🎯 Let's set your first financial goal!\n\n"
            "What would you like to name your goal?"
        )
        return GOAL_NAME
    
    return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button callbacks for goal actions."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_goal":
        await query.edit_message_text(
            "🎯 Let's set a new financial goal!\n\n"
            "What would you like to name your goal?"
        )
        return GOAL_NAME
    
    elif query.data == "update_progress":
        goals = get_user_goals(update.effective_user.id)
        if not goals:
            await query.edit_message_text("You don't have any active goals to update.")
            return ConversationHandler.END
        
        keyboard = []
        for goal_id, name, target, current, _, _, _ in goals:
            progress = (current / target) * 100 if target > 0 else 0
            keyboard.append([InlineKeyboardButton(
                f"{name} (${current:.2f}/${target:.2f} - {progress:.1f}%)",
                callback_data=f"update_{goal_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Select a goal to update its progress:",
            reply_markup=reply_markup
        )
        return GOAL_NAME  # We'll handle the update in the next callback
    
    elif query.data == "complete_goal":
        goals = get_user_goals(update.effective_user.id)
        if not goals:
            await query.edit_message_text("You don't have any active goals to complete.")
            return ConversationHandler.END
        
        keyboard = []
        for goal_id, name, target, current, _, _, _ in goals:
            progress = (current / target) * 100 if target > 0 else 0
            keyboard.append([InlineKeyboardButton(
                f"{name} (${current:.2f}/${target:.2f} - {progress:.1f}%)",
                callback_data=f"complete_{goal_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Select a goal to mark as completed:",
            reply_markup=reply_markup
        )
        return GOAL_NAME  # We'll handle the completion in the next callback
    
    elif query.data == "delete_goal":
        goals = get_user_goals(update.effective_user.id)
        if not goals:
            await query.edit_message_text("You don't have any active goals to delete.")
            return ConversationHandler.END
        
        keyboard = []
        for goal_id, name, target, current, _, _, _ in goals:
            progress = (current / target) * 100 if target > 0 else 0
            keyboard.append([InlineKeyboardButton(
                f"{name} (${current:.2f}/${target:.2f} - {progress:.1f}%)",
                callback_data=f"delete_{goal_id}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Select a goal to delete:",
            reply_markup=reply_markup
        )
        return GOAL_NAME  # We'll handle the deletion in the next callback
    
    elif query.data.startswith("update_"):
        goal_id = int(query.data.split("_")[1])
        context.user_data['update_goal_id'] = goal_id
        await query.edit_message_text(
            "Enter the amount to add to your goal progress:"
        )
        return GOAL_AMOUNT
    
    elif query.data.startswith("complete_"):
        goal_id = int(query.data.split("_")[1])
        complete_goal(goal_id)
        await query.edit_message_text("✅ Goal marked as completed!")
        return ConversationHandler.END
    
    elif query.data.startswith("delete_"):
        goal_id = int(query.data.split("_")[1])
        delete_goal(goal_id)
        await query.edit_message_text("🗑️ Goal deleted successfully!")
        return ConversationHandler.END
    
    return ConversationHandler.END

async def goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the goal name."""
    if update.callback_query:
        # Handle goal update amount
        try:
            amount = float(update.callback_query.message.text)
            goal_id = context.user_data.get('update_goal_id')
            if goal_id:
                update_goal_progress(goal_id, amount)
                await update.callback_query.edit_message_text(
                    f"✅ Added ${amount:.2f} to your goal progress!"
                )
                return ConversationHandler.END
        except ValueError:
            await update.callback_query.edit_message_text(
                "❌ Please enter a valid number."
            )
            return GOAL_AMOUNT
    else:
        context.user_data['goal_name'] = update.message.text
        await update.message.reply_text(
            "💰 What's your target amount? (e.g., 1000.00):"
        )
        return GOAL_AMOUNT

async def goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the goal amount."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Please enter a positive amount.")
            return GOAL_AMOUNT
        
        context.user_data['goal_amount'] = amount
        
        await update.message.reply_text(
            "📅 When do you want to achieve this goal? (YYYY-MM-DD) or send /skip:"
        )
        return GOAL_DEADLINE
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return GOAL_AMOUNT

async def goal_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the goal deadline."""
    if update.message.text == "/skip":
        context.user_data['goal_deadline'] = None
    else:
        try:
            # Validate date format
            datetime.strptime(update.message.text, "%Y-%m-%d")
            context.user_data['goal_deadline'] = update.message.text
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid date in YYYY-MM-DD format or /skip.")
            return GOAL_DEADLINE
    
    await update.message.reply_text(
        "📝 What category does this goal belong to? (e.g., Savings, Travel, Education) or send /skip:"
    )
    return GOAL_CATEGORY

async def goal_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the goal category and save the goal."""
    if update.message.text == "/skip":
        category = None
    else:
        category = update.message.text
    
    # Store data before clearing
    goal_name = context.user_data['goal_name']
    goal_amount = context.user_data['goal_amount']
    goal_deadline = context.user_data['goal_deadline']
    
    # Add goal to database
    add_goal(
        user_id=update.effective_user.id,
        name=goal_name,
        target_amount=goal_amount,
        deadline=goal_deadline,
        category=category
    )
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Goal created successfully!\n\n"
        f"Name: {goal_name}\n"
        f"Target: ${goal_amount:.2f}\n"
        f"Deadline: {goal_deadline if goal_deadline else 'Not set'}\n"
        f"Category: {category if category else 'Not set'}"
    )
    return ConversationHandler.END

async def cancel_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the goal creation conversation."""
    context.user_data.clear()
    await update.message.reply_text("❌ Goal creation cancelled.")
    return ConversationHandler.END

def get_goal_conversation_handler() -> ConversationHandler:
    """Get the goal conversation handler."""
    return ConversationHandler(
        entry_points=[CommandHandler("goal", goal)],
        states={
            GOAL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_name),
                CallbackQueryHandler(button_callback)
            ],
            GOAL_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_amount),
                CallbackQueryHandler(button_callback)
            ],
            GOAL_DEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_deadline),
                CommandHandler("skip", goal_deadline)
            ],
            GOAL_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_category),
                CommandHandler("skip", goal_category)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_goal)]
    ) 