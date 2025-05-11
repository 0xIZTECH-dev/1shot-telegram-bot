# 1Shot API Documentation

## Transaction Endpoints

Transaction endpoints are the core of the 1Shot API. They are RESTful endpoints configured to call smart contract functions on the blockchain.

### Configuration Requirements

- Provisioned and funded escrow wallet
- Target blockchain network
- Contract address
- Function name
- Input parameters
- (Optional) Webhook URL

### Parameter Types

1. **Primitive Types**

   - Basic types like uint, bool, address
   - Can be Static or Dynamic

2. **Array Types**

   - Collection of same type elements
   - Must be Dynamic

3. **Struct Types**
   - Collection of different types
   - Must be Dynamic

### Static vs Dynamic Parameters

- **Static**: Hardcoded in endpoint configuration
- **Dynamic**: Passed in API request payload

### Webhook Payload Structure

```json
{
  "eventName": "BusinessCreated",
  "data": {
    "businessId": "string",
    "chain": number,
    "transactionExecutionId": "string",
    "transactionReceipt": {
      "blockHash": "string",
      "blockNumber": number,
      "contractAddress": "string",
      "from": "string",
      "gasUsed": "string",
      "hash": "string",
      "logs": [],
      "status": number,
      "to": "string"
    }
  },
  "timestamp": number,
  "apiVersion": number,
  "signature": "string"
}
```

### Webhook Signature Verification

- Uses ed25519 signature scheme
- Signature included in payload
- Public key available in transaction details
- Base64 encoded ed25519 public key

## Triggering a Transaction

To execute a transaction on the blockchain, you need to make a POST request to the transaction endpoint. There are two ways to do this:

### 1. Using the SDK (Recommended)

```python
# Execute the transaction
execution = await oneshot_client.transactions.execute(
    transaction_id=transaction_endpoint_id,
    params={
        "param1": value1,
        "param2": value2,
        # Additional parameters as configured in the endpoint
    },
    memo=memo_json_string  # Optional transaction memo
)
```

### 2. Using Direct HTTP Request

```bash
curl -X POST https://api.1shotapi.com/v0/transactions/{TRANSACTION_ENDPOINT_ID}/execute \
    -H "Authorization: Bearer YOUR_BEARER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"params": {"to": "0xE936e8FAf4A5655469182A49a505055B71C17604", "value": "1000000000000000000"}}' | jq .
```

Where:

- `TRANSACTION_ENDPOINT_ID` is the ID of the transaction endpoint you want to call
- `YOUR_BEARER_TOKEN` is the JWT authentication token
- The JSON object under `params` contains the input data configured for the transaction endpoint
- For token transfers, `value` is typically in Wei (10^18 Wei = 1 ETH/Token)

The response will include a transaction execution ID that you can use to track the status of the transaction.

## Listing Transaction Endpoints

You can retrieve a list of all transaction endpoints configured under your organization.

### 1. Using the SDK (Recommended)

```python
# List all transaction endpoints
transaction_endpoints = await oneshot_client.transactions.list(
    business_id=BUSINESS_ID,
    params={
        "chain_id": "11155111",  # Optional: Filter by chain ID
        "name": "Endpoint Name"  # Optional: Filter by endpoint name
    }
)

# Access the first endpoint
if transaction_endpoints.response:
    endpoint = transaction_endpoints.response[0]
    endpoint_id = endpoint.id
    endpoint_name = endpoint.name
    # ... other endpoint properties
```

### 2. Using Direct HTTP Request

```bash
curl -X GET https://api.1shotapi.com/v0/business/{ORGANIZATION_ID}/transactions \
    -H "Authorization: Bearer YOUR_BEARER_TOKEN" | jq .
```

You can also filter the results using query parameters:

```bash
curl -X GET "https://api.1shotapi.com/v0/business/{ORGANIZATION_ID}/transactions?chain_id=11155111&name=MyEndpoint" \
    -H "Authorization: Bearer YOUR_BEARER_TOKEN" | jq .
```

The response contains an array of transaction endpoint objects with details like ID, name, contract address, function name, and more.
