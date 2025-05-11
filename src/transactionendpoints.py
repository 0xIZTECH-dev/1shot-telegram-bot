import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from oneshot import oneshot_client, BUSINESS_ID

logger = logging.getLogger(__name__)

async def list_transaction_endpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available transaction endpoints for the organization."""
    try:
        # Show a loading message
        loading_msg = await update.message.reply_text(
            "🔍 Fetching transaction endpoints...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Fetch all transaction endpoints
        transaction_endpoints = await oneshot_client.transactions.list(
            business_id=BUSINESS_ID,
            params={}  # Empty params to get all endpoints
        )
        
        if not transaction_endpoints.response or len(transaction_endpoints.response) == 0:
            await loading_msg.edit_text(
                "❌ No transaction endpoints found for your organization.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Build a formatted message with all endpoints
        message = "📋 *Available Transaction Endpoints*\n\n"
        
        for endpoint in transaction_endpoints.response:
            chain_name = get_chain_name(endpoint.chain_id) if hasattr(endpoint, 'chain_id') else "Unknown"
            
            message += f"*ID:* `{endpoint.id}`\n"
            message += f"*Name:* {endpoint.name}\n"
            message += f"*Network:* {chain_name}\n"
            message += f"*Contract:* `{endpoint.contract_address[:6]}...{endpoint.contract_address[-4:]}`\n"
            message += f"*Function:* `{endpoint.function_name}`\n"
            
            # Add parameters if they exist
            if hasattr(endpoint, 'parameters') and endpoint.parameters:
                message += "*Parameters:*\n"
                for param in endpoint.parameters:
                    param_type = param.type if hasattr(param, 'type') else "Unknown"
                    message += f"  • `{param.name}` ({param_type})\n"
            
            message += "\n---\n\n"
        
        # Edit the loading message with the endpoint information
        await loading_msg.edit_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in list_transaction_endpoints: {e}")
        await update.message.reply_text(
            "❌ An error occurred while fetching transaction endpoints. Please try again later.",
            parse_mode=ParseMode.MARKDOWN
        )

def get_chain_name(chain_id: str) -> str:
    """Get the human-readable name for a blockchain network ID."""
    chain_names = {
        "1": "Ethereum Mainnet",
        "11155111": "Sepolia Testnet",
        "5": "Goerli Testnet",
        "137": "Polygon Mainnet",
        "80001": "Mumbai Testnet",
        "43114": "Avalanche C-Chain",
        "42161": "Arbitrum One",
        "10": "Optimism"
    }
    return chain_names.get(chain_id, f"Chain ID {chain_id}")

def get_transaction_endpoints_handler():
    """Return the command handler for the /endpoints command."""
    return CommandHandler("endpoints", list_transaction_endpoints) 