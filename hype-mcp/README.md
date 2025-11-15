# Hyperliquid Lava RPC MCP Server

An MCP (Model Context Protocol) server that provides comprehensive tools for analyzing the Hyperliquid blockchain using Lava Network's high-performance RPC API endpoints.

## Features

This MCP server implements **Tier 1 tools** - direct API wrappers for Hyperliquid chain analysis:

### Chain & Network
- `get_chain_info` - Aggregate chain information (chainId, netVersion, clientVersion, syncing status)
- `check_node_sync_status` - Check node sync status and progress

### Blocks
- `get_block` - Get block by number or hash
- `get_latest_block` - Get the latest block
- `get_block_transactions` - Extract transactions array from a block

### Transactions
- `get_transaction` - Get transaction by hash
- `get_transaction_receipt` - Get transaction receipt by hash
- `estimate_transaction_gas` - Estimate gas for a transaction

### Accounts
- `get_account_balance` - Get account balance
- `get_account_nonce` - Get account transaction count (nonce)
- `get_contract_code` - Get contract code at address
- `get_storage_at` - Get storage value at address and position

### Calls & Execution
- `call_contract` - Call a contract method (eth_call)
- `query_logs` - Query event logs (eth_getLogs)

### Gas & Fees
- `get_gas_price` - Get current gas price (cached)
- `get_fee_history` - Get fee history for a block range

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Install dependencies:
```bash
uv sync
```

2. Set environment variables (optional):
```bash
export LAVA_RPC_URL="https://your-lava-rpc-endpoint"
export HYPERLIQUID_NETWORK="mainnet"  # or "testnet"
```

If `LAVA_RPC_URL` is not set, the server will use a default Lava endpoint. You should configure your own endpoint from [Lava Network](https://accounts.lavanet.xyz/).

### Running the Server

The server can be run using the MCP CLI:

```bash
uv run mcp-server hype-mcp.hype-server stdio
```

Or if you have FastMCP installed globally:
```bash
uv run python -m mcp.server.fastmcp hype-mcp.hype-server stdio
```

For development/testing, you can also use the MCP Inspector:
```bash
uv run mcp-inspector hype-mcp.hype-server
```

## Configuration

The server can be configured via environment variables:

- `LAVA_RPC_URL`: Lava RPC endpoint URL (required)
- `HYPERLIQUID_NETWORK`: Network name - "mainnet" or "testnet" (default: "mainnet")

## Response Format

All tools return responses in the following standardized format:

```json
{
  "success": boolean,
  "data": object | array,
  "metadata": {
    "rpc_calls": number,
    "execution_time": milliseconds,
    "cached": boolean
  },
  "errors": array | null
}
```

## Usage Examples

### Get Chain Info
```python
result = await get_chain_info()
# Returns: chainId, netVersion, clientVersion, syncing status
```

### Get Latest Block
```python
result = await get_latest_block(full_transactions=True)
# Returns: Full block data with transaction objects
```

### Get Account Balance
```python
result = await get_account_balance("0x...", "latest")
# Returns: Balance in hex and decimal (wei)
```

### Query Event Logs
```python
filter_obj = {
    "fromBlock": "0x0",
    "toBlock": "latest",
    "address": "0x...",
    "topics": []
}
result = await query_logs(filter_obj)
# Returns: Array of matching log entries
```

## Technical Details

- **Caching**: `eth_chainId` and `eth_gasPrice` are cached for 60 seconds to reduce RPC calls
- **Error Handling**: All tools include comprehensive error handling and return structured error responses
- **Performance**: Response metadata includes RPC call count and execution time for monitoring

## Development

This is a Tier 1 implementation. Future enhancements will include:
- Tier 2: Compound actions (transaction management, account analysis, etc.)
- Tier 3: Agent-friendly workflows (monitoring, validation, reporting)

## License

MIT

