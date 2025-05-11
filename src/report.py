import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from database import get_user_expenses, get_user_budgets, get_user_goals
from aichat import OPENAI_AVAILABLE # So we can check if AI is available

logger = logging.getLogger(__name__)

# Attempt to import openai, handle if not available
if OPENAI_AVAILABLE:
    import openai

REPORT_SYSTEM_PROMPT = \
"""
You are Penny, a financial assistant. You have been provided with the user's recent expenses,
active budgets, and active financial goals. Your task is to generate a comprehensive
financial report.

The report should:
1.  Briefly summarize overall spending.
2.  Compare spending against relevant budgets, highlighting areas where the user is on track or overspending.
3.  Assess progress towards financial goals based on current savings and targets.
4.  Offer actionable insights and suggestions for better financial management.
5.  Be encouraging and easy to understand.

Present the report in a clear, well-structured format. Use Markdown for formatting if it helps readability (e.g., bolding, bullet points).
"""

async def generate_financial_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a financial report for the user using their expenses, budgets, and goals data."""
    if not OPENAI_AVAILABLE:
        await update.message.reply_text(
            "I'm sorry, but my AI capabilities for generating reports are not available right now. "
            "Please try again later."
        )
        return

    user_id = update.effective_user.id
    await update.message.reply_text("🔍 Generating your financial report, please wait a moment...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # 1. Fetch data
        # For expenses, let's fetch a larger limit for a more comprehensive report, e.g., last 50
        expenses = get_user_expenses(user_id, limit=50)
        budgets = get_user_budgets(user_id)
        goals = get_user_goals(user_id, status='active') # Ensure we get active goals

        if not expenses and not budgets and not goals:
            await update.message.reply_text(
                "I couldn't find any financial data (expenses, budgets, or goals) for you. "
                "Please add some data using /expense, /budget, or /goal before requesting a report."
            )
            return

        # 2. Format data for the AI
        report_data_summary = "Here is your financial data:\n\n"

        if expenses:
            report_data_summary += "**Recent Expenses (last 50 or fewer):**\n"
            for expense in expenses:
                # amount, category, description, date, payment_method
                desc = f", Description: {expense[2]}" if expense[2] else ""
                report_data_summary += f"- Amount: ${expense[0]:.2f}, Category: {expense[1]}{desc}, Date: {expense[3].split(' ')[0]}\n"
            report_data_summary += "\n"
        else:
            report_data_summary += "No recent expenses found.\n\n"

        if budgets:
            report_data_summary += "**Active Budgets:**\n"
            for budget in budgets:
                # id, category, amount, period, start_date, end_date
                report_data_summary += f"- Category: {budget[1]}, Amount: ${budget[2]:.2f}, Period: {budget[3]}, Ends: {budget[5]}\n"
            report_data_summary += "\n"
        else:
            report_data_summary += "No active budgets found.\n\n"

        if goals:
            report_data_summary += "**Active Goals:**\n"
            for goal in goals:
                # id, name, target_amount, current_amount, deadline, category, status
                deadline_info = f", Deadline: {goal[4]}" if goal[4] else ""
                report_data_summary += f"- Name: {goal[1]}, Target: ${goal[2]:.2f}, Current: ${goal[3]:.2f}{deadline_info}\n"
            report_data_summary += "\n"
        else:
            report_data_summary += "No active goals found.\n"

        # 3. Construct messages for OpenAI
        messages = [
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": report_data_summary}
        ]

        # 4. Call OpenAI API
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo", # Or a newer model if available and preferred
            messages=messages,
            max_tokens=1000,  # Reports might be longer
            temperature=0.7,
            top_p=0.95
        )

        ai_report = response.choices[0].message.content

        # 5. Send report to user
        await update.message.reply_text(ai_report, parse_mode=ParseMode.MARKDOWN)

    except openai.error.OpenAIError as e: # More specific error handling for OpenAI
        logger.error(f"OpenAI API error while generating report for user {user_id}: {e}")
        await update.message.reply_text(
            "I encountered an issue with the AI service while trying to generate your report. "
            "Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"Error generating financial report for user {user_id}: {e}")
        await update.message.reply_text(
            "I'm sorry, something went wrong while generating your report. Please try again later."
        )

def get_report_handler() -> CommandHandler:
    """Returns the CommandHandler for the /report command."""
    return CommandHandler("report", generate_financial_report) 