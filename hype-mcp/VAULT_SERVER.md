# Vault Server MCP Tools

MCP server for analyzing Hyperliquid vault deposit/withdrawal activity.

## Tools

### 1. `list_vault_addresses`
Returns a list of all known vault addresses.

**Returns:**
- `vaults`: List of vault addresses
- `total_count`: Total number of vaults
- `from_hardcoded`: Number of hardcoded addresses
- `from_transfers`: Number of addresses found in transfers
- `hardcoded_addresses`: List of hardcoded addresses

**Example:**
```python
result = await list_vault_addresses()
# Returns: {
#   "vaults": ["0x1234...", "0xabcd..."],
#   "total_count": 2,
#   ...
# }
```

### 2. `get_vault_activity`
Get deposit/withdrawal activity for vault(s).

**Parameters:**
- `vault_address` (optional): Specific vault address to filter by. If not provided, returns activity for all vaults.

**Returns:**
- `vaults`: List of vault activity objects with:
  - `vault`: Vault address
  - `deposit_count`: Number of deposits
  - `withdrawal_count`: Number of withdrawals
  - `total_deposits_usd`: Total deposits in USD (raw)
  - `total_deposits_usd_formatted`: Total deposits in USD (formatted)
  - `total_withdrawals_usd`: Total withdrawals in USD (raw)
  - `total_withdrawals_usd_formatted`: Total withdrawals in USD (formatted)
  - `net_flow_usd`: Net flow (deposits - withdrawals)
  - `net_flow_usd_formatted`: Net flow formatted
  - `transfer_count`: Total number of transfers
- `summary`: Aggregated statistics across all vaults
- `filtered_by_vault`: Boolean indicating if filtered by specific vault

**Example:**
```python
# Get activity for all vaults
result = await get_vault_activity()

# Get activity for specific vault
result = await get_vault_activity(vault_address="0x1234...")
```

### 3. `get_delegation_info`
Get delegation information aggregated by validator address.

**Returns:**
- `validators`: List of validator activity objects with:
  - `validator`: Validator address
  - `delegation_count`: Number of delegations
  - `undelegation_count`: Number of undelegations
  - `total_delegated_wei`: Total delegated amount in wei (raw)
  - `total_delegated_wei_formatted`: Total delegated amount in ETH (formatted)
  - `total_undelegated_wei`: Total undelegated amount in wei (raw)
  - `total_undelegated_wei_formatted`: Total undelegated amount in ETH (formatted)
  - `net_delegated_wei`: Net delegated (delegated - undelegated)
  - `net_delegated_wei_formatted`: Net delegated formatted
  - `total_operations`: Total delegation operations
- `summary`: Aggregated statistics across all validators

**Example:**
```python
result = await get_delegation_info()
# Returns aggregated delegation stats per validator
```

## Integration with Log Processor

The tools call functions from `hyperliquid_log_processor.py`:

**`get_vault_transfers()`** returns:
```python
[
    {
        "vault": "0x...",      # Vault address
        "isDeposit": True,     # True for deposit, False for withdrawal
        "usd": 1000000000      # USD amount (in wei/raw format)
    },
    ...
    ]
```

**`get_delegations()`** returns:
```python
[
    {
        "validator": "0x...",      # Validator address
        "isUndelegate": False,     # True for undelegation, False for delegation
        "wei": 1000000000          # Amount in wei
    },
    ...
]
```

## Hardcoded Vault Addresses

The server includes a hardcoded list of known vault addresses in `KNOWN_VAULT_ADDRESSES`. These are combined with addresses discovered from vault transfers.

To update the hardcoded list, edit `vault-server.py`:
```python
KNOWN_VAULT_ADDRESSES = [
    "0x1234567890123456789012345678901234567890",
    # Add more vault addresses here
]
```

## Running the Server

```bash
# Set RPC URL if needed
export LAVA_RPC_URL="https://your-lava-endpoint"

# Run the server
uv run mcp-server hype-mcp.vault-server stdio
```

## Testing

Run the test script:
```bash
uv run python test_vault_server.py
```

## Response Format

All tools return responses in the standard format:
```json
{
  "success": boolean,
  "data": object,
  "metadata": {
    "execution_time": milliseconds
  },
  "errors": array | null
}
```

