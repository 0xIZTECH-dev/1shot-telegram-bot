# Implementation Plan for New 1Shot API Features

This document outlines the implementation plan for three new features utilizing the 1Shot API.

## I. Detailed Transaction Endpoint Information

- **Goal:** Allow users to get detailed information about a specific transaction endpoint beyond just its name.
- **Proposed Command:** `/endpointinfo <endpoint_name_or_id>`
  - Alternatively, enhance the existing `/endpoints` command to be interactive, allowing users to select an endpoint from the list to view its details.
- **Implementation Steps:**
  1.  **Create `src/endpointinfo.py`:**
      - Define an asynchronous function, e.g., `view_endpoint_details(update: Update, context: ContextTypes.DEFAULT_TYPE)`.
      - The function will expect an argument (endpoint name or ID) from the command.
      - Use `oneshot_client.transactions.list(business_id=BUSINESS_ID, params={"name": identifier})` if searching by name. If an exact ID is provided, it might be possible to use a more direct fetch if the SDK supports `oneshot_client.transactions.get(transaction_id=identifier)` or similar (requires SDK documentation check).
      - If an endpoint is found (or multiple match a partial name), format and present details such as:
        - Endpoint ID
        - Name
        - Contract Address
        - Function Name
        - Chain ID (and perhaps a human-readable network name)
        - A summary of its parameters (e.g., names, types, static/dynamic).
      - Handle cases where the endpoint is not found or if the API returns an error.
      - Provide a clear "not found" message or error message.
  2.  **Register Handler in `src/main.py`:**
      - Import the `view_endpoint_details` function (or a handler function that calls it) from `src/endpointinfo.py`.
      - Add a new `CommandHandler`: `application.add_handler(CommandHandler("endpointinfo", view_endpoint_details_handler))`.
  3.  **Update Help Text:**
      - Modify the help message in `src/hello.py` (or wherever `/help` is defined, likely `main.py`) to include the new `/endpointinfo` command and its usage.
- **Considerations:**
  - **Disambiguation:** If a name matches multiple endpoints, the bot could list them and ask the user to specify by ID, or present info for all matches if feasible.
  - **SDK capabilities:** Verify if the SDK allows fetching a single endpoint by its ID directly, as this would be more efficient than filtering a list if the ID is known.
  - **Output Formatting:** Ensure the details are presented in a readable way in the Telegram message.

## II. Transaction History/Status Check

- **Goal:** Enable users to check the status and details of a transaction they previously initiated using its execution ID.
- **Proposed Command:** `/txstatus <transaction_execution_id>`
- **Implementation Steps:**
  1.  **Create `src/transactionstatus.py`:**
      - Define an asynchronous function, e.g., `check_transaction_status(update: Update, context: ContextTypes.DEFAULT_TYPE)`.
      - The function will expect the `transaction_execution_id` as an argument.
      - Use `oneshot_client.transactions.get_execution(transaction_execution_id=execution_id)` (this method name is an assumption; the actual SDK method needs to be verified. The `WebhookPayload` structure gives clues about available data).
      - If the execution details are retrieved, format and display key information:
        - Current Status (e.g., "Success", "Pending", "Failed", "Processing")
        - Transaction Hash (with a link to a block explorer like Etherscan: `https://sepolia.etherscan.io/tx/<hash>`)
        - Block Number (if mined)
        - Gas Used
        - Timestamp
        - Any error messages if the transaction failed.
      - Handle errors gracefully (e.g., execution ID not found, API errors).
  2.  **Register Handler in `src/main.py`:**
      - Import the handler function from `src/transactionstatus.py`.
      - Add `application.add_handler(CommandHandler("txstatus", check_transaction_status_handler))`.
  3.  **Update Help Text:** Add `/txstatus` to the help message.
- **Considerations:**
  - **Execution ID Source:** Users will need to get the `transaction_execution_id`. This is typically returned when a transaction is first executed (e.g., our `/deploytoken` or `/tokentransfer` could be modified to explicitly show this ID to the user, or log it).
  - **Data Persistence (Optional enhancement):** For a better user experience, the bot could store recent `transaction_execution_id`s initiated by a user (e.g., in `context.user_data` temporarily, or in `penny.db` for more persistent history) and allow them to query recent transactions without needing the full ID.
  - **Interpreting Status:** Ensure the status reported by the API is translated into user-friendly terms.

## III. Wallet Balance Details

- **Goal:** Provide users with more detailed information about the escrow wallet(s) associated with the configured `BUSINESS_ID`.
- **Proposed Command:** `/walletdetails`
- **Implementation Steps:**
  1.  **Create `src/walletdetails.py`:**
      - Define an asynchronous function, e.g., `show_wallet_details(update: Update, context: ContextTypes.DEFAULT_TYPE)`.
      - Use `await oneshot_client.wallets.list(BUSINESS_ID, params={"chain_id": "11155111"})`. We might also call it without `chain_id` to see if there are wallets on other chains.
      - Iterate through the `wallets.response` list. For each wallet object, format and display:
        - Wallet ID
        - Account Address
        - Chain ID (e.g., 11155111) and its common name (e.g., "Sepolia")
        - Available Balance (e.g., `wallet.account_balance_details.balance`)
        - Currency Symbol (e.g., `wallet.account_balance_details.currency_symbol`)
        - Other available details like `created_at` or `type` if present and relevant.
      - Handle cases where no wallets are found for the `BUSINESS_ID` or if there's an API error.
  2.  **Register Handler in `src/main.py`:**
      - Import the handler function from `src/walletdetails.py`.
      - Add `application.add_handler(CommandHandler("walletdetails", show_wallet_details_handler))`.
  3.  **Update Help Text:** Add `/walletdetails` to the help message.
- **Considerations:**
  - **Relation to Startup Check:** The `lifespan` function in `main.py` already performs a similar check for the Sepolia escrow wallet. This command will make this information available on-demand and potentially for other wallets/chains if configured.
  - **Multiple Wallets:** If the API can return multiple wallets (e.g., on different chains or multiple wallets on the same chain for the same business), ensure the output is clearly formatted for each.
  - **Sensitivity:** Wallet addresses and balances are sensitive; ensure the command is appropriate for the bot's intended users. (This is already implicitly handled as it's tied to the bot's `BUSINESS_ID`).
