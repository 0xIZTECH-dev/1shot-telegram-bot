from telegram import Chat, Update
from telegram.ext import ContextTypes, ConversationHandler
from decimal import Decimal, ROUND_DOWN

from oneshot import (
    oneshot_client,
    BUSINESS_ID
)

from objects import ConversationState

import re
import os
from typing import Dict, Any

CALLBACK_URL = os.getenv("TUNNEL_BASE_URL") + "/1shot"

# Python doesn't have a built-in BigInt type, so we use a string to represent large integers
def convert_to_wei(amount: str, decimals: int = 18) -> str:
    """Convert a string amount to wei with specified decimals (default is 18 for ETH and most tokens)."""
    try:
        # Handle floating point values
        if '.' in amount:
            # Split by decimal point
            whole, fractional = amount.split('.')
            # Pad fractional part with zeros if needed
            fractional = fractional.ljust(decimals, '0')[:decimals]
            # Combine whole and fractional parts
            wei_value = whole + fractional
            # Remove leading zeros
            wei_value = wei_value.lstrip('0')
            # If result is empty, it was zero
            if not wei_value:
                return '0'
            return wei_value
        else:
            # For whole numbers, append zeros
            value = int(amount)
            if value < 0:
                raise ValueError("Negative value")
            return str(value) + '0' * decimals
    except ValueError:
        raise ValueError("Invalid value: must be a non-negative number.")

# handy function to check if a user entered a non-neggative value
def is_nonnegative_integer(value: str) -> bool:
    """Check if the given string represents a positive integer."""
    try:
        return int(value) >= 0
    except ValueError:
        return False

# handy function to check if a user entered a valid Ethereum address
def is_valid_ethereum_address(address: str) -> bool:
    """Check if the given string is a valid Ethereum address."""
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))

# Can be used as a general fallback function to end conversation flows
async def canceler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("bye 👋")
    context.user_data[ConversationState.START_OVER] = False
    return ConversationHandler.END

def get_chain_id_from_network_name(network_name: str) -> str | None:
    """Returns the chain ID for a given network name."""
    network_name_lower = network_name.lower()
    if network_name_lower == "sepolia":
        return "11155111"
    elif network_name_lower == "mainnet" or network_name_lower == "ethereum":
        return "1"
    # Add other common networks and their chain IDs
    elif network_name_lower == "goerli":
        return "5"
    elif network_name_lower == "polygon":
        return "137"
    elif network_name_lower == "mumbai":
        return "80001"
    # You can expand this list or use a more robust lookup method
    else:
        return None # Or raise an error for unknown network

def get_token_deployer_endpoint_creation_payload(chain_id: str, contract_address: str, escrow_wallet_id: str) -> Dict[str, str]:
     return {
        "chain": chain_id,
        "contractAddress": contract_address,
        "escrowWalletId": escrow_wallet_id,
        "name": f"1Shot Demo Sepolia Token Deployer",
        "description": f"This deploys ERC20 tokens on the Sepolia testnet.",
        "functionName": "deployToken",
        "callbackUrl": f"{CALLBACK_URL}",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "admin",
                "type": "address",
                "index": 0,
            },
            {
                "name": "name",
                "type": "string",
                "index": 1
            },
            {
                "name": "ticker",
                "type": "string",
                "index": 2
            },
            {
                "name": "premint",
                "type": "uint",
                "index": 3
            }
        ],
        "outputs": []
    }

def format_wei(wei_amount: str | int, decimals: int) -> str:
    """Converts a Wei amount to a human-readable string, given the token's decimals."""
    if decimals <= 0:
        # For tokens with 0 decimals, or if decimals is unknown and defaults to 0 incorrectly.
        return str(wei_amount) # Return as is, or handle as an error if appropriate.

    amount_decimal = Decimal(str(wei_amount))
    divisor = Decimal(10) ** decimals
    readable_amount = amount_decimal / divisor
    
    # Format to a reasonable number of decimal places, e.g., 6 or 8, or strip trailing zeros
    # For simplicity, let's convert to string and let Python handle precision initially
    # For more control, you might use f-strings with specific precision or quantize
    return str(readable_amount.normalize()) # normalize() removes trailing zeros