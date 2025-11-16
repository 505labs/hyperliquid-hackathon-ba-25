"""
Hyperliquid Lava RPC MCP Server - Demo Tools
Implements demo-specific tools for trading analysis and monitoring.
"""

import os
import sys
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from collections import defaultdict
from mcp.server.fastmcp import FastMCP
import httpx

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads variables from .env file
    print("✓ Loaded .env file")
except ImportError:
    print("⚠ python-dotenv not installed - .env file won't be loaded")
    print("  Install with: uv add python-dotenv")
    print("  Or set environment variables directly")

# Setup logging - goes to stderr (safe for stdio MCP servers)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Important: use stderr, not stdout!
)
logger = logging.getLogger(__name__)

# Helper function for debug prints (goes to stderr)
def debug_print(*args, **kwargs):
    """Print to stderr for debugging (safe for MCP stdio transport)."""
    print(*args, **kwargs, file=sys.stderr, flush=True)

# Create an MCP server
mcp = FastMCP("Hyperliquid Lava RPC - Demo Tools")

# Configuration
LAVA_RPC_URL = os.getenv("LAVA_RPC_URL", "https://eth1.lava.build/lava-referer-8b51600b-b188-4c52-8c57-c65d3a9be5af/")
BLOCKS_PER_24H = 7200  # ~7200 blocks at 12s/block for 24 hours
BLOCK_TIME_SECONDS = 12


class RPCClient:
    """Client for making JSON-RPC calls to Lava endpoints."""
    
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def call(self, method: str, params: List[Any] = None) -> Any:
        """Make a JSON-RPC call."""
        if params is None:
            params = []
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        try:
            response = await self.client.post(self.url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                raise Exception(f"RPC Error: {result['error']}")
            
            return result.get("result")
        except httpx.HTTPError as e:
            raise Exception(f"HTTP Error: {str(e)}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global RPC client instance
_rpc_client: Optional[RPCClient] = None


async def get_rpc_client() -> RPCClient:
    """Get or create RPC client instance."""
    global _rpc_client
    if _rpc_client is None:
        _rpc_client = RPCClient(LAVA_RPC_URL)
    return _rpc_client


def format_response(
    data: Any,
    rpc_calls: int = 1,
    execution_time_ms: float = 0,
    cached: bool = False,
    errors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Format response according to spec."""
    return {
        "success": errors is None or len(errors) == 0,
        "data": data,
        "metadata": {
            "rpc_calls": rpc_calls,
            "execution_time": execution_time_ms,
            "cached": cached
        },
        "errors": errors if errors else None
    }


def hex_to_int(hex_str: str) -> int:
    """Convert hex string to integer."""
    if isinstance(hex_str, str):
        return int(hex_str, 16) if hex_str.startswith("0x") else int(hex_str)
    return hex_str


def normalize_address(address: str) -> str:
    """Normalize address to 0x-prefixed hex string."""
    if not address.startswith("0x"):
        return "0x" + address
    return address.lower()


# ============================================================================
# Demo Tool 1: Top Profitable Traders
# ============================================================================

@mcp.tool()
async def get_top_profitable_traders(
    hours: int = 24,
    top_n: int = 5,
    min_transaction_value_eth: float = 0.1
) -> Dict[str, Any]:
    """
    Find the top N most profitable traders in the last X hours.
    
    Args:
        hours: Number of hours to analyze (default: 24)
        top_n: Number of top traders to return (default: 5)
        min_transaction_value_eth: Minimum transaction value in ETH to consider (default: 0.1)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "traders": [],
        "analysis": {}
    }
    rpc_calls = 0
    
    try:
        # Step 1: Get current block number
        latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
        rpc_calls += 1
        latest_block = hex_to_int(latest_block_data.get("number", "0x0"))

        debug_print(f"[get_top_profitable_traders] Current block: {latest_block}")
        
        # Step 2: Calculate block range for specified hours
        blocks_to_scan = int((hours * 3600) / BLOCK_TIME_SECONDS)
        start_block = max(0, latest_block - blocks_to_scan)
        debug_print(f"[get_top_profitable_traders] Step 2: Block range {start_block} to {latest_block} ({blocks_to_scan} blocks)")
        
        # For demo, limit to reasonable number of blocks to scan
        max_blocks_to_scan = 500  # Limit for demo performance
        if blocks_to_scan > max_blocks_to_scan:
            # Sample blocks instead of scanning all
            step = blocks_to_scan // max_blocks_to_scan
            blocks_to_scan = max_blocks_to_scan
        else:
            step = 1
        
        debug_print(f"[get_top_profitable_traders] Will scan {blocks_to_scan} blocks (sampling every {step} blocks)")

        # Step 3: Scan blocks for high-value transactions
        debug_print(f"[get_top_profitable_traders] Step 3: Scanning blocks for transactions >= {min_transaction_value_eth} ETH...")
        trader_stats = defaultdict(lambda: {
            "address": "",
            "total_volume_wei": 0,
            "total_volume_eth": 0.0,
            "transaction_count": 0,
            "sent_volume_wei": 0,
            "received_volume_wei": 0,
            "net_flow_wei": 0,
            "transactions": []
        })
        
        min_value_wei = int(min_transaction_value_eth * 1e18)
        
        # Sample blocks for performance
        blocks_scanned = 0
        for i in range(0, blocks_to_scan, step):
            block_num = start_block + i
            if block_num > latest_block:
                break
            
            try:
                block = await rpc.call("eth_getBlockByNumber", [hex(block_num), True])
                rpc_calls += 1
                blocks_scanned += 1

                debug_print(f"[get_top_profitable_traders] Scanning block {block_num}")
                
                if block and "transactions" in block:

                    for tx in block.get("transactions", []):
                        if isinstance(tx, dict):
                            value_wei = hex_to_int(tx.get("value", "0x0"))
                            
                            # Only consider transactions above minimum value
                            if value_wei >= min_value_wei:
                                from_addr = (tx.get("from") or "").lower()
                                to_addr = (tx.get("to") or "").lower()

                                if i%100 == 0:
                                    debug_print(f"[get_top_profitable_traders] Found transaction: {value_wei/1e18:.4f} ETH")
                                
                                if from_addr:
                                    trader_stats[from_addr]["address"] = from_addr
                                    trader_stats[from_addr]["total_volume_wei"] += value_wei
                                    trader_stats[from_addr]["sent_volume_wei"] += value_wei
                                    trader_stats[from_addr]["transaction_count"] += 1
                                    trader_stats[from_addr]["net_flow_wei"] -= value_wei
                                
                                if to_addr:
                                    trader_stats[to_addr]["address"] = to_addr
                                    trader_stats[to_addr]["total_volume_wei"] += value_wei
                                    trader_stats[to_addr]["received_volume_wei"] += value_wei
                                    trader_stats[to_addr]["transaction_count"] += 1
                                    trader_stats[to_addr]["net_flow_wei"] += value_wei
                                
                                # Store transaction for top traders
                                if from_addr or to_addr:
                                    tx_data = {
                                        "hash": tx.get("hash"),
                                        "blockNumber": block_num,
                                        "from": from_addr,
                                        "to": to_addr,
                                        "value": value_wei,
                                        "valueEth": value_wei / 1e18
                                    }
                                    if from_addr:
                                        trader_stats[from_addr]["transactions"].append(tx_data)
                                    if to_addr:
                                        trader_stats[to_addr]["transactions"].append(tx_data)
                
                # Small delay to avoid rate limiting
                # if blocks_scanned % 50 == 0:
                    # await asyncio.sleep(0.1)
                    
            except Exception as e:
                # Continue on individual block errors
                continue
        
        # Step 4: Calculate profit metrics and rank
        traders_list = []
        for addr, stats in trader_stats.items():
            stats["total_volume_eth"] = stats["total_volume_wei"] / 1e18
            stats["sent_volume_eth"] = stats["sent_volume_wei"] / 1e18
            stats["received_volume_eth"] = stats["received_volume_wei"] / 1e18
            stats["net_flow_eth"] = stats["net_flow_wei"] / 1e18
            
            # Profit metric: net flow (positive = received more than sent)
            # For demo, we'll use net flow as profitability indicator
            traders_list.append(stats)
        
        # Step 5: Rank by net flow (profitability)
        debug_print(f"[get_top_profitable_traders] Step 5: Ranking {len(traders_list)} traders...")
        traders_list.sort(key=lambda x: x["net_flow_wei"], reverse=True)
        top_traders = traders_list[:top_n]
        debug_print(f"[get_top_profitable_traders] Found top {len(top_traders)} traders")
        
        # Get current activity for top traders
        for trader in top_traders:
            addr = trader["address"]
            try:
                # Get current balance
                balance = await rpc.call("eth_getBalance", [addr, "latest"])
                rpc_calls += 1
                trader["current_balance_wei"] = hex_to_int(balance)
                trader["current_balance_eth"] = trader["current_balance_wei"] / 1e18
                
                # Get nonce (transaction count)
                nonce = await rpc.call("eth_getTransactionCount", [addr, "latest"])
                rpc_calls += 1
                trader["total_transactions"] = hex_to_int(nonce)
                
                # Get latest transaction
                if trader["transactions"]:
                    latest_tx = max(trader["transactions"], key=lambda x: x["blockNumber"])
                    trader["latest_transaction"] = latest_tx
                    trader["activity_status"] = "active"
                else:
                    trader["activity_status"] = "inactive"
                    
            except Exception as e:
                trader["activity_status"] = "unknown"
                trader["error"] = str(e)
        
        data["traders"] = top_traders
        data["analysis"] = {
            "timeframe_hours": hours,
            "blocks_scanned": blocks_scanned,
            "total_blocks_in_range": blocks_to_scan,
            "sampling_rate": step,
            "min_transaction_value_eth": min_transaction_value_eth,
            "total_unique_traders": len(traders_list),
            "analysis_timestamp": time.time()
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Demo Tool 2: Monitor Address for Trades
# ============================================================================

# Store monitoring state
_monitoring_state: Dict[str, Dict[str, Any]] = {}


@mcp.tool()
async def start_monitoring_address(
    address: str,
    poll_interval_seconds: float = 5.0,
    max_polls: int = 20
) -> Dict[str, Any]:
    """
    Start monitoring an address for new transactions/trades.
    Polls the address and detects new transactions.
    
    Args:
        address: Address to monitor (0x-prefixed hex string)
        poll_interval_seconds: Time between polls in seconds (default: 5.0)
        max_polls: Maximum number of polls before stopping (default: 20)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "alerts": [],
        "monitoring_session": {}
    }
    rpc_calls = 0
    
    try:
        address = normalize_address(address)
        
        # Step 1: Get initial state
        initial_nonce = await rpc.call("eth_getTransactionCount", [address, "latest"])
        rpc_calls += 1
        initial_nonce_int = hex_to_int(initial_nonce)
        
        initial_balance = await rpc.call("eth_getBalance", [address, "latest"])
        rpc_calls += 1
        initial_balance_wei = hex_to_int(initial_balance)
        
        # Step 2: Set up polling loop
        alerts = []
        last_nonce = initial_nonce_int
        last_balance = initial_balance_wei
        
        for poll_num in range(1, max_polls + 1):
            try:
                # Step 3: Check for new transactions
                current_nonce = await rpc.call("eth_getTransactionCount", [address, "latest"])
                rpc_calls += 1
                current_nonce_int = hex_to_int(current_nonce)
                
                current_balance = await rpc.call("eth_getBalance", [address, "latest"])
                rpc_calls += 1
                current_balance_wei = hex_to_int(current_balance)
                
                # Step 4: Detect new transactions
                if current_nonce_int > last_nonce:
                    # New transaction detected!
                    new_tx_count = current_nonce_int - last_nonce
                    
                    # Get latest transactions
                    latest_block = await rpc.call("eth_getBlockByNumber", ["latest", False])
                    rpc_calls += 1
                    latest_block_num = hex_to_int(latest_block.get("number", "0x0"))
                    
                    # Try to get transaction details from recent blocks
                    tx_details = []
                    for i in range(min(10, new_tx_count * 2)):  # Check recent blocks
                        try:
                            block = await rpc.call("eth_getBlockByNumber", [hex(latest_block_num - i), True])
                            rpc_calls += 1
                            
                            if block and "transactions" in block:
                                for tx in block.get("transactions", []):
                                    if isinstance(tx, dict):
                                        tx_from = (tx.get("from") or "").lower()
                                        tx_to = (tx.get("to") or "").lower()
                                        
                                        if tx_from == address or tx_to == address:
                                            tx_detail = {
                                                "hash": tx.get("hash"),
                                                "blockNumber": hex_to_int(tx.get("blockNumber", "0x0")),
                                                "from": tx_from,
                                                "to": tx_to,
                                                "value": hex_to_int(tx.get("value", "0x0")),
                                                "valueEth": hex_to_int(tx.get("value", "0x0")) / 1e18,
                                                "gas": hex_to_int(tx.get("gas", "0x0")),
                                                "gasPrice": hex_to_int(tx.get("gasPrice", "0x0")),
                                                "input": tx.get("input", "0x")
                                            }
                                            
                                            # Check if this is a trade (has input data or significant value)
                                            if len(tx_detail["input"]) > 2 or tx_detail["valueEth"] > 0.01:
                                                tx_detail["type"] = "trade" if len(tx_detail["input"]) > 2 else "transfer"
                                            else:
                                                tx_detail["type"] = "transfer"
                                            
                                            tx_details.append(tx_detail)
                                            
                                            if len(tx_details) >= new_tx_count:
                                                break
                                
                                if len(tx_details) >= new_tx_count:
                                    break
                        except:
                            continue
                    
                    # Step 5: Create alert with context
                    balance_change = (current_balance_wei - last_balance) / 1e18
                    
                    alert = {
                        "timestamp": time.time(),
                        "poll_number": poll_num,
                        "alert_type": "new_transaction",
                        "address": address,
                        "new_transaction_count": new_tx_count,
                        "previous_nonce": last_nonce,
                        "current_nonce": current_nonce_int,
                        "balance_change_eth": balance_change,
                        "previous_balance_eth": last_balance / 1e18,
                        "current_balance_eth": current_balance_wei / 1e18,
                        "transactions": tx_details,
                        "message": f"🚨 ALERT: {new_tx_count} new transaction(s) detected for {address[:10]}...{address[-8:]}"
                    }
                    
                    alerts.append(alert)
                    
                    last_nonce = current_nonce_int
                    last_balance = current_balance_wei
                
                # Wait before next poll
                if poll_num < max_polls:
                    await asyncio.sleep(poll_interval_seconds)
                    
            except Exception as e:
                # Continue polling on error
                errors.append(f"Poll {poll_num} error: {str(e)}")
                continue
        
        data["alerts"] = alerts
        data["monitoring_session"] = {
            "address": address,
            "polls_completed": max_polls,
            "poll_interval_seconds": poll_interval_seconds,
            "initial_nonce": initial_nonce_int,
            "final_nonce": last_nonce,
            "initial_balance_eth": initial_balance_wei / 1e18,
            "final_balance_eth": last_balance / 1e18,
            "total_alerts": len(alerts),
            "monitoring_duration_seconds": time.time() - start_time
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def check_address_status(address: str) -> Dict[str, Any]:
    """
    Quick check of address status - balance, nonce, and recent activity.
    Useful for checking what an address is doing right now.
    
    Args:
        address: Address to check (0x-prefixed hex string)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        address = normalize_address(address)
        
        # Get current state
        balance = await rpc.call("eth_getBalance", [address, "latest"])
        rpc_calls += 1
        balance_wei = hex_to_int(balance)
        
        nonce = await rpc.call("eth_getTransactionCount", [address, "latest"])
        rpc_calls += 1
        nonce_int = hex_to_int(nonce)
        
        # Get latest block to check recent activity
        latest_block = await rpc.call("eth_getBlockByNumber", ["latest", False])
        rpc_calls += 1
        latest_block_num = hex_to_int(latest_block.get("number", "0x0"))
        
        # Check last 5 blocks for activity
        recent_activity = []
        for i in range(5):
            try:
                block = await rpc.call("eth_getBlockByNumber", [hex(latest_block_num - i), True])
                rpc_calls += 1
                
                if block and "transactions" in block:
                    for tx in block.get("transactions", []):
                        if isinstance(tx, dict):
                            tx_from = (tx.get("from") or "").lower()
                            tx_to = (tx.get("to") or "").lower()
                            
                            if tx_from == address or tx_to == address:
                                recent_activity.append({
                                    "hash": tx.get("hash"),
                                    "blockNumber": hex_to_int(tx.get("blockNumber", "0x0")),
                                    "direction": "sent" if tx_from == address else "received",
                                    "valueEth": hex_to_int(tx.get("value", "0x0")) / 1e18
                                })
                                if len(recent_activity) >= 3:  # Limit to 3 most recent
                                    break
                
                if len(recent_activity) >= 3:
                    break
            except:
                continue
        
        data = {
            "address": address,
            "current_balance_wei": balance_wei,
            "current_balance_eth": balance_wei / 1e18,
            "transaction_count": nonce_int,
            "recent_activity": recent_activity,
            "status": "active" if recent_activity else "inactive",
            "checked_at": time.time()
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)
