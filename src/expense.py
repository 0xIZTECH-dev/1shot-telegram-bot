from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from database import add_expense, get_user_expenses, get_user_categories
from objects import ConversationState

# States for the expense conversation
EXPENSE_AMOUNT, EXPENSE_CATEGORY, EXPENSE_DESCRIPTION = range(3)

# Default categories with emojis
DEFAULT_CATEGORIES = {
    "🍔 Food & Dining": ["Restaurant", "Groceries", "Coffee", "Takeout"],
    "🏠 Housing": ["Rent", "Utilities", "Maintenance", "Furniture"],
    "🚗 Transportation": ["Gas", "Public Transit", "Car Maintenance", "Parking"],
    "🛍️ Shopping": ["Clothing", "Electronics", "Home Goods", "Personal Care"],
    "💊 Healthcare": ["Medical", "Pharmacy", "Insurance", "Fitness"],
    "🎮 Entertainment": ["Movies", "Games", "Subscriptions", "Events"],
    "📚 Education": ["Books", "Courses", "Software", "Supplies"],
    "✈️ Travel": ["Flights", "Hotels", "Activities", "Transportation"],
    "💰 Income": ["Salary", "Freelance", "Investments", "Gifts"],
    "📱 Bills": ["Phone", "Internet", "Streaming", "Other"]
}

async def expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the expense tracking conversation."""
    await update.message.reply_text(
        "💰 Let's add a new expense!\n\n"
        "Please enter the amount (e.g., 25.50):"
    )
    return EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the expense amount."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Please enter a positive amount.")
            return EXPENSE_AMOUNT
        
        context.user_data['expense_amount'] = amount
        
        # Get existing categories
        user_categories = get_user_categories(update.effective_user.id)
        
        # Create keyboard with main categories
        keyboard = []
        for main_category in DEFAULT_CATEGORIES.keys():
            keyboard.append([InlineKeyboardButton(main_category, callback_data=f"main_{main_category}")])
        
        # Add user's custom categories if any
        if user_categories:
            keyboard.append([InlineKeyboardButton("📋 Your Categories", callback_data="user_categories")])
        
        keyboard.append([InlineKeyboardButton("➕ New Category", callback_data="new_category")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📝 Select a category:",
            reply_markup=reply_markup
        )
        return EXPENSE_CATEGORY
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return EXPENSE_AMOUNT

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the expense category selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_category":
        await query.edit_message_text(
            "📝 Please enter a new category name:"
        )
        return EXPENSE_CATEGORY
    
    if query.data == "user_categories":
        # Show user's custom categories
        user_categories = get_user_categories(update.effective_user.id)
        keyboard = []
        for category in user_categories:
            keyboard.append([InlineKeyboardButton(category, callback_data=f"category_{category}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📋 Your custom categories:",
            reply_markup=reply_markup
        )
        return EXPENSE_CATEGORY
    
    if query.data == "back_to_main":
        # Return to main categories
        keyboard = []
        for main_category in DEFAULT_CATEGORIES.keys():
            keyboard.append([InlineKeyboardButton(main_category, callback_data=f"main_{main_category}")])
        keyboard.append([InlineKeyboardButton("📋 Your Categories", callback_data="user_categories")])
        keyboard.append([InlineKeyboardButton("➕ New Category", callback_data="new_category")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📝 Select a category:",
            reply_markup=reply_markup
        )
        return EXPENSE_CATEGORY
    
    if query.data.startswith("main_"):
        # Show subcategories for the selected main category
        main_category = query.data.replace("main_", "")
        keyboard = []
        for subcategory in DEFAULT_CATEGORIES[main_category]:
            keyboard.append([InlineKeyboardButton(subcategory, callback_data=f"category_{subcategory}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📝 Select a subcategory for {main_category}:",
            reply_markup=reply_markup
        )
        return EXPENSE_CATEGORY
    
    if query.data.startswith("category_"):
        # Handle final category selection
        category = query.data.replace("category_", "")
        context.user_data['expense_category'] = category
        
        await query.edit_message_text(
            f"💬 Add a description for your {category} expense (or send /skip to leave it empty):"
        )
        return EXPENSE_DESCRIPTION
    
    # If we get here, it's a new category name
    context.user_data['expense_category'] = query.data
    
    await query.edit_message_text(
        f"💬 Add a description for your {query.data} expense (or send /skip to leave it empty):"
    )
    return EXPENSE_DESCRIPTION

async def expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the expense description."""
    if update.message.text == "/skip":
        description = None
    else:
        description = update.message.text
    
    # Add expense to database
    add_expense(
        user_id=update.effective_user.id,
        amount=context.user_data['expense_amount'],
        category=context.user_data['expense_category'],
        description=description
    )
    
    # Store values before clearing context
    amount = context.user_data['expense_amount']
    category = context.user_data['expense_category']
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        f"✅ Expense added successfully!\n\n"
        f"Amount: ${amount:.2f}\n"
        f"Category: {category}\n"
        f"Description: {description if description else 'None'}"
    )
    return ConversationHandler.END

async def cancel_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the expense tracking conversation."""
    context.user_data.clear()
    await update.message.reply_text("❌ Expense tracking cancelled.")
    return ConversationHandler.END

def get_expense_conversation_handler() -> ConversationHandler:
    """Get the expense conversation handler."""
    return ConversationHandler(
        entry_points=[CommandHandler("expense", expense)],
        states={
            EXPENSE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)
            ],
            EXPENSE_CATEGORY: [
                CallbackQueryHandler(expense_category),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)
            ],
            EXPENSE_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_description),
                CommandHandler("skip", expense_description)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_expense)]
    ) 