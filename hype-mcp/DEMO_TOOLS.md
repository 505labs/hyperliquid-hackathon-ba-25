# Demo Tools - Tier 3 MCP Server

This document describes the demo-specific tools implemented in `hype-server-3.py` for the Hyperliquid hackathon.

## Tools Overview

### 1. `get_top_profitable_traders`
**Use Case**: "Who are the top 5 most profitable traders in the last 24 hours and what are they doing right now?"

**Workflow**:
1. Gets current block number
2. Calculates 24h block range (~7200 blocks at 12s/block)
3. Scans blocks for high-value transactions
4. Groups by address and calculates profit metrics
5. Ranks and returns top N traders with current activity

**Parameters**:
- `hours` (default: 24): Number of hours to analyze
- `top_n` (default: 5): Number of top traders to return
- `min_transaction_value_eth` (default: 0.1): Minimum transaction value to consider

**Returns**:
- Top N traders ranked by profitability (net flow)
- Current balance and transaction count for each
- Latest transaction details
- Activity status

**Example Response**:
```json
{
  "success": true,
  "data": {
    "traders": [
      {
        "address": "0x...",
        "total_volume_eth": 150.5,
        "net_flow_eth": 25.3,
        "transaction_count": 12,
        "current_balance_eth": 100.0,
        "activity_status": "active",
        "latest_transaction": {...}
      }
    ],
    "analysis": {
      "timeframe_hours": 24,
      "blocks_scanned": 500,
      "total_unique_traders": 45
    }
  }
}
```

### 2. `start_monitoring_address`
**Use Case**: "Monitor address 0x123... and alert me when they make a trade"

**Workflow**:
1. Sets up polling loop for address
2. Tracks latest transaction count/nonce
3. Detects new transactions
4. Analyzes transaction details
5. Sends alert with context

**Parameters**:
- `address`: Address to monitor (0x-prefixed)
- `poll_interval_seconds` (default: 5.0): Time between polls
- `max_polls` (default: 20): Maximum polls before stopping

**Returns**:
- Array of alerts when new transactions detected
- Transaction details (hash, value, type)
- Balance changes
- Monitoring session summary

**Example Response**:
```json
{
  "success": true,
  "data": {
    "alerts": [
      {
        "alert_type": "new_transaction",
        "new_transaction_count": 1,
        "balance_change_eth": 5.2,
        "transactions": [
          {
            "hash": "0x...",
            "type": "trade",
            "valueEth": 5.2
          }
        ],
        "message": "🚨 ALERT: 1 new transaction(s) detected..."
      }
    ],
    "monitoring_session": {
      "polls_completed": 20,
      "total_alerts": 3,
      "monitoring_duration_seconds": 100.5
    }
  }
}
```

### 3. `check_address_status`
**Helper tool**: Quick check of what an address is doing right now.

**Parameters**:
- `address`: Address to check

**Returns**:
- Current balance
- Transaction count
- Recent activity (last 3 transactions)
- Activity status

## Performance Optimizations

For demo purposes, the tools include several optimizations:

1. **Block Sampling**: Instead of scanning all blocks, samples every Nth block
2. **Limited Range**: Caps maximum blocks scanned to 500 for performance
3. **Transaction Filtering**: Only considers transactions above minimum value threshold
4. **Rate Limiting**: Small delays between batch RPC calls

## Usage Examples

### Find Top Traders
```python
result = await get_top_profitable_traders(
    hours=24,
    top_n=5,
    min_transaction_value_eth=0.1
)
```

### Monitor Address
```python
result = await start_monitoring_address(
    address="0x1234567890abcdef1234567890abcdef12345678",
    poll_interval_seconds=5.0,
    max_polls=20
)
```

### Quick Status Check
```python
result = await check_address_status(
    address="0x1234567890abcdef1234567890abcdef12345678"
)
```

## Running the Server

```bash
# Set RPC URL
export LAVA_RPC_URL="https://your-lava-endpoint"

# Run the server
uv run mcp-server hype-mcp.hype-server-3 stdio
```

## Demo Considerations

- **Performance**: Tools are optimized for demo speed, not exhaustive analysis
- **Accuracy**: Results are based on sampled data for performance
- **Real-time**: Monitoring tool polls in real-time but has limits for demo
- **Scalability**: For production, would need more sophisticated indexing and caching

