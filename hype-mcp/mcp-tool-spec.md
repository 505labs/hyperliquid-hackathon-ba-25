
# Hyperliquid Lava RPC MCP Tool Specification

## Tier 1: Direct API Wrappers
Simple 1:1 mappings to RPC methods. Return raw or lightly formatted responses.

### Chain & Network
- **get_chain_info**: Aggregate eth_chainId, net_version, web3_clientVersion, eth_syncing
- **check_node_sync_status**: Boolean sync status + progress from eth_syncing

### Blocks
- **get_block**: eth_getBlockByNumber / eth_getBlockByHash (params: block_id, full_transactions)
- **get_latest_block**: eth_getBlockByNumber with "latest"
- **get_block_transactions**: Extract transactions array from block

### Transactions
- **get_transaction**: eth_getTransactionByHash (params: tx_hash)
- **get_transaction_receipt**: eth_getTransactionReceipt (params: tx_hash)
- **estimate_transaction_gas**: eth_estimateGas (params: transaction_object)

### Accounts
- **get_account_balance**: eth_getBalance (params: address, block)
- **get_account_nonce**: eth_getTransactionCount (params: address, block)
- **get_contract_code**: eth_getCode (params: address, block)
- **get_storage_at**: eth_getStorageAt (params: address, position, block)

### Calls & Execution
- **call_contract**: eth_call (params: transaction_object, block)
- **query_logs**: eth_getLogs (params: filter_object)

### Gas & Fees
- **get_gas_price**: eth_gasPrice
- **get_fee_history**: eth_feeHistory (params: block_count, newest_block, reward_percentiles)

---

## Tier 2: Compound Actions
Combine multiple RPC calls into single logical operations.

### Transaction Management
- **wait_for_transaction_confirmation**: Poll eth_getTransactionReceipt until confirmed + N blocks (params: tx_hash, confirmations, timeout)
- **track_transaction_status**: Monitor tx through lifecycle: pending → mined → confirmed (params: tx_hash, poll_interval)
- **get_transaction_cost_analysis**: Receipt + gas price + calculate USD cost estimate (params: tx_hash)

### Account Analysis
- **get_account_activity**: Scan block range for all txs involving address (params: address, start_block, end_block)
- **analyze_account_holdings**: Balance + nonce + code check + recent tx count (params: address)
- **track_balance_changes**: Balance snapshots across block range (params: address, block_range)

### Block Analytics
- **get_block_range**: Fetch multiple sequential blocks efficiently (params: start_block, end_block, full_tx)
- **analyze_gas_trends**: Process eth_feeHistory into statistical summary (params: block_count, percentiles)
- **get_network_health**: Sync status + latest block time + gas price trend (no params)

### Smart Contract Tools
- **decode_contract_events**: eth_getLogs + parse common event signatures (params: contract, event_signatures, block_range)
- **analyze_contract_activity**: All interactions with contract in timeframe (params: contract_address, block_range)
- **compare_gas_estimates**: Run eth_call + eth_estimateGas, compare results (params: transaction_object)

### Hyperliquid-Specific
- **get_system_transactions**: Fetch system txs from block range (params: block_range)
- **analyze_system_tx_patterns**: Frequency, types, gas usage of system txs (params: block_range)

---

## Tier 3: Agent-Friendly Workflows
High-level semantic operations for autonomous agents.

### Monitoring
**monitor_address**
- Params: address, alert_on[balance_change|new_tx|contract_interaction], threshold, poll_interval
- Continuously poll and report significant events
- Return: Event stream or aggregated alerts

### Validation
**simulate_and_validate_transaction**
- Params: from, to, data, value, checks[sufficient_balance|gas_estimate|call_success]
- Pre-flight validation before real tx submission
- Return: validation_results, warnings, estimated_cost

### Reporting
**generate_activity_report**
- Params: address, start_block, end_block, include[tx_summary|gas_spent|contract_interactions|balance_timeline]
- Comprehensive historical analysis
- Return: structured report object

### Gas Optimization
**optimize_gas_strategy**
- Params: transaction, urgency[low|medium|high], max_wait_time
- Analyze eth_feeHistory + recommend optimal gas price
- Return: recommended_gas, estimated_wait, cost_comparison

### Analytics
**analyze_block_range**
- Params: start, end, metrics[avg_gas|tx_count|system_tx_ratio|top_addresses]
- Statistical analysis across blocks
- Return: aggregated metrics object

### Event Listening
**subscribe_to_events**
- Params: contracts[], event_signatures[], filters{}, action[notify|aggregate|analyze]
- Intelligent event monitoring with filtering
- Return: event stream or analysis

### Transaction Tracing
**trace_transaction_flow**
- Params: starting_tx, max_depth, follow[internal_calls|related_addresses|token_flows]
- Map transaction relationships and call chains
- Return: transaction graph/tree

### Network Comparison
**compare_networks**
- Params: operation, params, networks[mainnet|testnet], compare[gas_prices|block_times|behavior]
- Execute same query on both networks
- Return: comparative analysis object

---

## Implementation Notes

### Priority Order
1. **Tier 1**: All tools (15-20) - Foundation layer
2. **Tier 2**: Priority subset (6-8 tools) - Transaction management, account analysis, gas trends
3. **Tier 3**: Select 2-3 differentiators - Recommend: monitor_address, simulate_and_validate_transaction, generate_activity_report

### Technical Requirements
- All RPC calls via Lava endpoints (mainnet/testnet)
- Handle pagination for large block ranges
- Implement exponential backoff for polling operations
- Cache eth_chainId and eth_gasPrice with TTL
- Return structured JSON responses
- Include error handling for RPC failures

### Response Format Standard
```json
{
  "success": boolean,
  "data": object | array,
  "metadata": {
    "rpc_calls": number,
    "execution_time": ms,
    "cached": boolean
  },
  "errors": array | null
}
```
