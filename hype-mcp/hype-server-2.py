"""
Hyperliquid Lava RPC MCP Server - Tier 2
Implements Tier 2 compound action tools for Hyperliquid chain analysis using Lava RPC endpoints.
These tools combine multiple RPC calls into single logical operations.
"""

import os
import time
import json
import asyncio
from typing import Any, Dict, List, Optional, Union

from asyncio.log import logger
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

# Create an MCP server
mcp = FastMCP("Hyperliquid Lava RPC - Tier 2")

# Configuration
LAVA_RPC_URL = os.getenv("LAVA_RPC_URL", "https://eth1.lava.build/lava-referer-8b51600b-b188-4c52-8c57-c65d3a9be5af/")
NETWORK = os.getenv("HYPERLIQUID_NETWORK", "mainnet")  # mainnet or testnet


print(f"LAVA_RPC_URL: {LAVA_RPC_URL}")
async def test_get_block() -> Dict[str, Any]:
    block = await get_rpc_client().call("eth_getBlockByNumber", ["latest", True])
    return block


# Simple cache
_cache: Dict[str, tuple[Any, float]] = {}
CACHE_TTL = 60  # seconds


class RPCClient:
    """Client for making JSON-RPC calls to Lava endpoints."""
    
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def call(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
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


def normalize_block(block: Union[str, int]) -> str:
    """Normalize block identifier to hex string."""
    if isinstance(block, str):
        if block.startswith("0x"):
            return block
        elif block in ["latest", "earliest", "pending"]:
            return block
        else:
            try:
                return hex(int(block))
            except ValueError:
                return block
    else:
        return hex(int(block))


def normalize_address(address: str) -> str:
    """Normalize address to 0x-prefixed hex string."""
    if not address.startswith("0x"):
        return "0x" + address
    return address


def hex_to_int(hex_str: str) -> int:
    """Convert hex string to integer."""
    if isinstance(hex_str, str):
        return int(hex_str, 16) if hex_str.startswith("0x") else int(hex_str)
    return hex_str


# ============================================================================
# Tier 2: Transaction Management Tools
# ============================================================================

@mcp.tool()
async def wait_for_transaction_confirmation(
    tx_hash: str,
    confirmations: int = 1,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Poll eth_getTransactionReceipt until transaction is confirmed + N blocks.
    
    Args:
        tx_hash: Transaction hash (0x-prefixed hex string)
        confirmations: Number of confirmations required (default: 1)
        timeout: Maximum time to wait in seconds (default: 300)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        receipt = None
        latest_block = None
        receipt_block = None
        
        while time.time() - start_time < timeout:
            # Get receipt
            receipt = await rpc.call("eth_getTransactionReceipt", [tx_hash])
            rpc_calls += 1
            
            if receipt:
                receipt_block = hex_to_int(receipt.get("blockNumber", "0x0"))
                
                # Get latest block
                latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
                rpc_calls += 1
                latest_block = hex_to_int(latest_block_data.get("number", "0x0"))
                
                confirmations_count = latest_block - receipt_block
                
                if confirmations_count >= confirmations:
                    data["status"] = "confirmed"
                    data["receipt"] = receipt
                    data["confirmations"] = confirmations_count
                    data["requiredConfirmations"] = confirmations
                    data["blockNumber"] = receipt_block
                    data["latestBlock"] = latest_block
                    break
            else:
                # Transaction not yet mined
                await asyncio.sleep(2)
        
        if not receipt:
            data["status"] = "timeout"
            data["message"] = f"Transaction not confirmed within {timeout} seconds"
        elif data.get("status") != "confirmed":
            data["status"] = "pending"
            data["message"] = "Transaction mined but not enough confirmations yet"
        
        data["waitTime"] = time.time() - start_time
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def track_transaction_status(
    tx_hash: str,
    poll_interval: float = 2.0
) -> Dict[str, Any]:
    """
    Monitor transaction through lifecycle: pending → mined → confirmed.
    
    Args:
        tx_hash: Transaction hash (0x-prefixed hex string)
        poll_interval: Time between polls in seconds (default: 2.0)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "status": "pending",
        "history": []
    }
    rpc_calls = 0
    
    try:
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        max_polls = 30  # Limit to prevent infinite loops
        poll_count = 0
        
        while poll_count < max_polls:
            # Get transaction
            tx = await rpc.call("eth_getTransactionByHash", [tx_hash])
            rpc_calls += 1
            
            # Get receipt
            receipt = await rpc.call("eth_getTransactionReceipt", [tx_hash])
            rpc_calls += 1
            
            status_entry = {
                "timestamp": time.time(),
                "poll": poll_count + 1
            }
            
            if not tx:
                status_entry["status"] = "not_found"
                data["history"].append(status_entry)
                break
            elif not receipt:
                status_entry["status"] = "pending"
                status_entry["transaction"] = tx
            else:
                # Transaction is mined
                status_entry["status"] = "mined"
                status_entry["transaction"] = tx
                status_entry["receipt"] = receipt
                status_entry["blockNumber"] = hex_to_int(receipt.get("blockNumber", "0x0"))
                status_entry["gasUsed"] = hex_to_int(receipt.get("gasUsed", "0x0"))
                status_entry["statusCode"] = receipt.get("status", "0x1")
                
                # Get latest block to check confirmations
                latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
                rpc_calls += 1
                latest_block = hex_to_int(latest_block_data.get("number", "0x0"))
                receipt_block = hex_to_int(receipt.get("blockNumber", "0x0"))
                confirmations = latest_block - receipt_block
                
                status_entry["confirmations"] = confirmations
                status_entry["latestBlock"] = latest_block
                
                if confirmations > 0:
                    status_entry["status"] = "confirmed"
                    data["status"] = "confirmed"
                    data["history"].append(status_entry)
                    break
            
            data["history"].append(status_entry)
            data["status"] = status_entry["status"]
            
            if status_entry["status"] == "mined":
                break
            
            await asyncio.sleep(poll_interval)
            poll_count += 1
        
        data["totalPolls"] = poll_count + 1
        data["finalStatus"] = data["status"]
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_transaction_cost_analysis(tx_hash: str) -> Dict[str, Any]:
    """
    Analyze transaction cost: receipt + gas price + calculate USD cost estimate.
    
    Args:
        tx_hash: Transaction hash (0x-prefixed hex string)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        # Get receipt
        receipt = await rpc.call("eth_getTransactionReceipt", [tx_hash])
        rpc_calls += 1
        
        if not receipt:
            raise Exception("Transaction receipt not found")
        
        # Get transaction
        tx = await rpc.call("eth_getTransactionByHash", [tx_hash])
        rpc_calls += 1
        
        # Get gas price (use transaction gas price or current gas price)
        gas_price_hex = tx.get("gasPrice") if tx else None
        if not gas_price_hex:
            gas_price_hex = await rpc.call("eth_gasPrice")
            rpc_calls += 1
        
        gas_price = hex_to_int(gas_price_hex)
        gas_used = hex_to_int(receipt.get("gasUsed", "0x0"))
        
        # Calculate costs
        total_gas_cost = gas_price * gas_used
        total_gas_cost_eth = total_gas_cost / 1e18
        
        # Estimate USD cost (placeholder - would need price oracle in production)
        # Using a rough estimate: 1 ETH = $3000
        eth_price_usd = 3000.0
        total_cost_usd = total_gas_cost_eth * eth_price_usd
        
        data["transactionHash"] = tx_hash
        data["gasUsed"] = gas_used
        data["gasPrice"] = gas_price
        data["gasPriceGwei"] = gas_price / 1e9
        data["totalGasCost"] = hex(total_gas_cost)
        data["totalGasCostWei"] = total_gas_cost
        data["totalGasCostEth"] = total_gas_cost_eth
        data["estimatedCostUSD"] = total_cost_usd
        data["ethPriceUSD"] = eth_price_usd
        data["blockNumber"] = hex_to_int(receipt.get("blockNumber", "0x0"))
        data["receipt"] = receipt
        data["transaction"] = tx
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 2: Account Analysis Tools
# ============================================================================

@mcp.tool()
async def get_account_activity(
    address: str,
    start_block: Union[str, int],
    end_block: Union[str, int] = "latest"
) -> Dict[str, Any]:
    """
    Scan block range for all transactions involving address.
    
    Args:
        address: Account address (0x-prefixed hex string)
        start_block: Starting block number
        end_block: Ending block number or "latest" (default: "latest")
    """

    logger.info(f"1111111111111: {address}")

    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "transactions": [],
        "sent": [],
        "received": []
    }
    rpc_calls = 0
    
    logger.info(f"HEREE!!!!!")

    try:
        address = normalize_address(address)
        start_block_norm = normalize_block(start_block)
        end_block_norm = normalize_block(end_block)
        
        # Get end block number if "latest"
        if end_block_norm == "latest":
            latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
            rpc_calls += 1
            end_block_num = hex_to_int(latest_block_data.get("number", "0x0"))
        else:
            end_block_num = hex_to_int(end_block_norm)
        
        start_block_num = hex_to_int(start_block_norm) if start_block_norm not in ["latest", "earliest", "pending"] else 0
        
        # Limit block range to prevent excessive RPC calls
        max_blocks = 1000
        if end_block_num - start_block_num > max_blocks:
            end_block_num = start_block_num + max_blocks
        
        # Scan blocks (sample every Nth block to avoid too many calls)
        step = max(1, (end_block_num - start_block_num) // 100)  # Sample up to 100 blocks
        
        for block_num in range(start_block_num, end_block_num + 1, step):
            block_hex = hex(block_num)
            block = await rpc.call("eth_getBlockByNumber", [block_hex, True])
            rpc_calls += 1
            
            if block and "transactions" in block:
                for tx in block["transactions"]:
                    if isinstance(tx, dict):
                        tx_from = (tx.get("from") or "").lower()
                        tx_to = (tx.get("to") or "").lower()
                        address_lower = address.lower()

                        logger.info(f"tx_from: {tx_from}")
                        logger.info(f"tx_to: {tx_to}")
                        logger.info(f"address_lower: {address_lower}")
                        
                        if tx_from == address_lower or tx_to == address_lower:
                            tx_data = {
                                "hash": tx.get("hash"),
                                "blockNumber": hex_to_int(tx.get("blockNumber", "0x0")),
                                "from": tx.get("from"),
                                "to": tx.get("to"),
                                "value": hex_to_int(tx.get("value", "0x0")),
                                "gas": hex_to_int(tx.get("gas", "0x0")),
                                "gasPrice": hex_to_int(tx.get("gasPrice", "0x0")),
                                "nonce": hex_to_int(tx.get("nonce", "0x0")),
                                "direction": "sent" if tx_from == address_lower else "received"
                            }
                            data["transactions"].append(tx_data)
                            
                            if tx_from == address_lower:
                                data["sent"].append(tx_data)
                            if tx_to == address_lower:
                                data["received"].append(tx_data)
        
        data["address"] = address
        data["blockRange"] = {
            "start": start_block_num,
            "end": end_block_num,
            "blocksScanned": len(range(start_block_num, end_block_num + 1, step))
        }
        data["summary"] = {
            "totalTransactions": len(data["transactions"]),
            "sentCount": len(data["sent"]),
            "receivedCount": len(data["received"])
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def analyze_account_holdings(address: str) -> Dict[str, Any]:
    """
    Analyze account: balance + nonce + code check + recent tx count.
    
    Args:
        address: Account address (0x-prefixed hex string)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        address = normalize_address(address)
        
        # Get balance
        balance = await rpc.call("eth_getBalance", [address, "latest"])
        rpc_calls += 1
        
        # Get nonce
        nonce = await rpc.call("eth_getTransactionCount", [address, "latest"])
        rpc_calls += 1
        
        # Get code (check if contract)
        code = await rpc.call("eth_getCode", [address, "latest"])
        rpc_calls += 1
        
        # Get latest block to estimate recent tx count
        latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
        rpc_calls += 1
        latest_block = hex_to_int(latest_block_data.get("number", "0x0"))
        
        # Count transactions in last 100 blocks (sampling)
        recent_tx_count = 0
        for i in range(max(0, latest_block - 100), latest_block + 1, 10):  # Sample every 10th block
            block = await rpc.call("eth_getBlockByNumber", [hex(i), True])
            rpc_calls += 1
            if block and "transactions" in block:
                for tx in block["transactions"]:
                    if isinstance(tx, dict):
                        tx_from = tx.get("from", "").lower()
                        tx_to = tx.get("to", "").lower()
                        if tx_from == address.lower() or tx_to == address.lower():
                            recent_tx_count += 1
        
        data["address"] = address
        data["balance"] = balance
        data["balanceWei"] = hex_to_int(balance)
        data["balanceEth"] = hex_to_int(balance) / 1e18
        data["nonce"] = nonce
        data["nonceDecimal"] = hex_to_int(nonce)
        data["isContract"] = code != "0x" and code != ""
        data["codeLength"] = len(code) - 2 if code.startswith("0x") else len(code)
        data["recentTransactionCount"] = recent_tx_count
        data["latestBlock"] = latest_block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def track_balance_changes(
    address: str,
    block_range: Dict[str, Union[str, int]]
) -> Dict[str, Any]:
    """
    Get balance snapshots across block range.
    
    Args:
        address: Account address (0x-prefixed hex string)
        block_range: Dict with "start" and "end" block numbers, or "step" for sampling interval
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "snapshots": []
    }
    rpc_calls = 0
    
    try:
        address = normalize_address(address)
        start_block = normalize_block(block_range.get("start", "0"))
        end_block = normalize_block(block_range.get("end", "latest"))
        step = block_range.get("step", 1)
        
        # Get end block number
        if end_block == "latest":
            latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
            rpc_calls += 1
            end_block_num = hex_to_int(latest_block_data.get("number", "0x0"))
        else:
            end_block_num = hex_to_int(end_block)
        
        start_block_num = hex_to_int(start_block) if start_block not in ["latest", "earliest", "pending"] else 0
        
        # Limit range
        max_blocks = 1000
        if end_block_num - start_block_num > max_blocks:
            step = max(step, (end_block_num - start_block_num) // max_blocks)
        
        # Sample blocks
        for block_num in range(start_block_num, end_block_num + 1, step):
            block_hex = hex(block_num)
            balance = await rpc.call("eth_getBalance", [address, block_hex])
            rpc_calls += 1
            
            snapshot = {
                "blockNumber": block_num,
                "balance": balance,
                "balanceWei": hex_to_int(balance),
                "balanceEth": hex_to_int(balance) / 1e18
            }
            data["snapshots"].append(snapshot)
        
        data["address"] = address
        data["blockRange"] = {
            "start": start_block_num,
            "end": end_block_num,
            "step": step,
            "snapshots": len(data["snapshots"])
        }
        
        # Calculate changes
        if len(data["snapshots"]) > 1:
            first_balance = data["snapshots"][0]["balanceWei"]
            last_balance = data["snapshots"][-1]["balanceWei"]
            data["balanceChange"] = last_balance - first_balance
            data["balanceChangeEth"] = data["balanceChange"] / 1e18
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 2: Block Analytics Tools
# ============================================================================

@mcp.tool()
async def get_block_range(
    start_block: Union[str, int],
    end_block: Union[str, int],
    full_tx: bool = False
) -> Dict[str, Any]:
    """
    Fetch multiple sequential blocks efficiently.
    
    Args:
        start_block: Starting block number
        end_block: Ending block number
        full_tx: If True, include full transaction objects (default: False)
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "blocks": []
    }
    rpc_calls = 0
    
    try:
        start_block_norm = normalize_block(start_block)
        end_block_norm = normalize_block(end_block)
        
        start_block_num = hex_to_int(start_block_norm) if start_block_norm not in ["latest", "earliest", "pending"] else 0
        end_block_num = hex_to_int(end_block_norm) if end_block_norm not in ["latest", "earliest", "pending"] else 0
        
        # Limit range
        max_blocks = 100
        if end_block_num - start_block_num > max_blocks:
            end_block_num = start_block_num + max_blocks
        
        # Fetch blocks
        for block_num in range(start_block_num, end_block_num + 1):
            block_hex = hex(block_num)
            block = await rpc.call("eth_getBlockByNumber", [block_hex, full_tx])
            rpc_calls += 1
            
            if block:
                block_summary = {
                    "number": hex_to_int(block.get("number", "0x0")),
                    "hash": block.get("hash"),
                    "timestamp": hex_to_int(block.get("timestamp", "0x0")),
                    "transactionCount": len(block.get("transactions", [])),
                    "gasUsed": hex_to_int(block.get("gasUsed", "0x0")),
                    "gasLimit": hex_to_int(block.get("gasLimit", "0x0"))
                }
                
                if full_tx:
                    block_summary["transactions"] = block.get("transactions", [])
                
                data["blocks"].append(block_summary)
        
        data["range"] = {
            "start": start_block_num,
            "end": end_block_num,
            "count": len(data["blocks"])
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def analyze_gas_trends(
    block_count: Union[int, str] = 20,
    percentiles: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Process eth_feeHistory into statistical summary.
    
    Args:
        block_count: Number of blocks to analyze (default: 20)
        percentiles: List of percentile values (default: [25, 50, 75, 90, 95])
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if percentiles is None:
            percentiles = [25, 50, 75, 90, 95]
        
        block_count_int = int(block_count) if isinstance(block_count, str) else block_count
        
        fee_history = await rpc.call("eth_feeHistory", [hex(block_count_int), "latest", percentiles])
        
        if fee_history:
            base_fees = [hex_to_int(bf) for bf in fee_history.get("baseFeePerGas", [])]
            gas_used_ratios = fee_history.get("gasUsedRatio", [])
            reward = fee_history.get("reward", [])
            
            # Calculate statistics
            if base_fees:
                data["baseFeeStats"] = {
                    "min": min(base_fees),
                    "max": max(base_fees),
                    "avg": sum(base_fees) / len(base_fees),
                    "median": sorted(base_fees)[len(base_fees) // 2]
                }
                data["baseFeeStatsGwei"] = {
                    "min": data["baseFeeStats"]["min"] / 1e9,
                    "max": data["baseFeeStats"]["max"] / 1e9,
                    "avg": data["baseFeeStats"]["avg"] / 1e9,
                    "median": data["baseFeeStats"]["median"] / 1e9
                }
            
            if gas_used_ratios:
                data["gasUsedRatioStats"] = {
                    "min": min(gas_used_ratios),
                    "max": max(gas_used_ratios),
                    "avg": sum(gas_used_ratios) / len(gas_used_ratios),
                    "median": sorted(gas_used_ratios)[len(gas_used_ratios) // 2]
                }
            
            # Process reward percentiles
            if reward:
                reward_stats = {}
                for i, percentile in enumerate(percentiles):
                    rewards_at_percentile = [hex_to_int(r[i]) if i < len(r) else 0 for r in reward if r]
                    if rewards_at_percentile:
                        reward_stats[f"p{int(percentile)}"] = {
                            "min": min(rewards_at_percentile),
                            "max": max(rewards_at_percentile),
                            "avg": sum(rewards_at_percentile) / len(rewards_at_percentile)
                        }
                        reward_stats[f"p{int(percentile)}Gwei"] = {
                            "min": reward_stats[f"p{int(percentile)}"]["min"] / 1e9,
                            "max": reward_stats[f"p{int(percentile)}"]["max"] / 1e9,
                            "avg": reward_stats[f"p{int(percentile)}"]["avg"] / 1e9
                        }
                data["rewardStats"] = reward_stats
            
            data["rawData"] = {
                "baseFeePerGas": base_fees,
                "gasUsedRatio": gas_used_ratios,
                "oldestBlock": hex_to_int(fee_history.get("oldestBlock", "0x0")),
                "reward": reward
            }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_network_health() -> Dict[str, Any]:
    """
    Get network health: sync status + latest block time + gas price trend.
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        # Get sync status
        syncing = await rpc.call("eth_syncing")
        rpc_calls += 1
        
        # Get latest block
        latest_block = await rpc.call("eth_getBlockByNumber", ["latest", False])
        rpc_calls += 1
        
        # Get gas price
        gas_price = await rpc.call("eth_gasPrice")
        rpc_calls += 1
        
        # Get fee history for trend
        fee_history = await rpc.call("eth_feeHistory", [hex(10), "latest", [50]])
        rpc_calls += 1
        
        # Process data
        is_syncing = isinstance(syncing, dict) if syncing else False
        is_synced = not is_syncing
        
        latest_block_num = hex_to_int(latest_block.get("number", "0x0")) if latest_block else 0
        latest_block_time = hex_to_int(latest_block.get("timestamp", "0x0")) if latest_block else 0
        current_time = int(time.time())
        block_age = current_time - latest_block_time
        
        gas_price_wei = hex_to_int(gas_price)
        
        # Calculate gas price trend
        gas_trend = "stable"
        if fee_history and "baseFeePerGas" in fee_history:
            base_fees = [hex_to_int(bf) for bf in fee_history["baseFeePerGas"]]
            if len(base_fees) >= 2:
                recent_avg = sum(base_fees[-3:]) / min(3, len(base_fees))
                older_avg = sum(base_fees[:3]) / min(3, len(base_fees))
                if recent_avg > older_avg * 1.1:
                    gas_trend = "increasing"
                elif recent_avg < older_avg * 0.9:
                    gas_trend = "decreasing"
        
        data["syncStatus"] = {
            "isSynced": is_synced,
            "isSyncing": is_syncing,
            "syncProgress": syncing if isinstance(syncing, dict) else None
        }
        data["latestBlock"] = {
            "number": latest_block_num,
            "timestamp": latest_block_time,
            "ageSeconds": block_age,
            "hash": latest_block.get("hash") if latest_block else None
        }
        data["gasPrice"] = {
            "wei": gas_price_wei,
            "gwei": gas_price_wei / 1e9
        }
        data["gasTrend"] = gas_trend
        data["healthStatus"] = "healthy" if is_synced and block_age < 60 else "degraded"
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 2: Smart Contract Tools
# ============================================================================

@mcp.tool()
async def decode_contract_events(
    contract: str,
    event_signatures: List[str],
    block_range: Dict[str, Union[str, int]]
) -> Dict[str, Any]:
    """
    Get logs and parse common event signatures.
    
    Args:
        contract: Contract address (0x-prefixed hex string)
        event_signatures: List of event signatures (e.g., ["Transfer(address,address,uint256)"])
        block_range: Dict with "fromBlock" and "toBlock"
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "events": [],
        "bySignature": {}
    }
    rpc_calls = 1
    
    try:
        contract = normalize_address(contract)
        from_block = normalize_block(block_range.get("fromBlock", "0"))
        to_block = normalize_block(block_range.get("toBlock", "latest"))
        
        # Build filter
        filter_obj = {
            "address": contract,
            "fromBlock": from_block,
            "toBlock": to_block
        }
        
        # Get logs
        logs = await rpc.call("eth_getLogs", [filter_obj])
        
        if logs:
            for log in logs:
                topics = log.get("topics", [])
                if topics:
                    event_signature = topics[0]  # First topic is usually the event signature hash
                    
                    event_data = {
                        "logIndex": hex_to_int(log.get("logIndex", "0x0")),
                        "transactionHash": log.get("transactionHash"),
                        "blockNumber": hex_to_int(log.get("blockNumber", "0x0")),
                        "blockHash": log.get("blockHash"),
                        "address": log.get("address"),
                        "topics": topics,
                        "data": log.get("data"),
                        "eventSignature": event_signature
                    }
                    
                    data["events"].append(event_data)
                    
                    # Group by signature
                    if event_signature not in data["bySignature"]:
                        data["bySignature"][event_signature] = []
                    data["bySignature"][event_signature].append(event_data)
        
        data["contract"] = contract
        data["blockRange"] = {
            "fromBlock": from_block,
            "toBlock": to_block
        }
        data["requestedSignatures"] = event_signatures
        data["summary"] = {
            "totalEvents": len(data["events"]),
            "uniqueSignatures": len(data["bySignature"])
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def analyze_contract_activity(
    contract_address: str,
    block_range: Dict[str, Union[str, int]]
) -> Dict[str, Any]:
    """
    Get all interactions with contract in timeframe.
    
    Args:
        contract_address: Contract address (0x-prefixed hex string)
        block_range: Dict with "fromBlock" and "toBlock"
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "interactions": [],
        "transactions": [],
        "logs": []
    }
    rpc_calls = 0
    
    try:
        contract_address = normalize_address(contract_address)
        from_block = normalize_block(block_range.get("fromBlock", "0"))
        to_block = normalize_block(block_range.get("toBlock", "latest"))
        
        # Get logs (events)
        filter_obj = {
            "address": contract_address,
            "fromBlock": from_block,
            "toBlock": to_block
        }
        logs = await rpc.call("eth_getLogs", [filter_obj])
        rpc_calls += 1
        
        if logs:
            data["logs"] = logs
            
            # Get unique transaction hashes
            tx_hashes = set()
            for log in logs:
                tx_hash = log.get("transactionHash")
                if tx_hash:
                    tx_hashes.add(tx_hash)
            
            # Get transaction details
            for tx_hash in list(tx_hashes)[:50]:  # Limit to 50 transactions
                tx = await rpc.call("eth_getTransactionByHash", [tx_hash])
                rpc_calls += 1
                
                if tx:
                    tx_data = {
                        "hash": tx.get("hash"),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "value": hex_to_int(tx.get("value", "0x0")),
                        "gas": hex_to_int(tx.get("gas", "0x0")),
                        "gasPrice": hex_to_int(tx.get("gasPrice", "0x0")),
                        "input": tx.get("input"),
                        "blockNumber": hex_to_int(tx.get("blockNumber", "0x0"))
                    }
                    data["transactions"].append(tx_data)
                    
                    # Create interaction record
                    interaction = {
                        "type": "transaction",
                        "transactionHash": tx_hash,
                        "from": tx.get("from"),
                        "value": hex_to_int(tx.get("value", "0x0")),
                        "blockNumber": hex_to_int(tx.get("blockNumber", "0x0")),
                        "timestamp": None  # Would need block timestamp
                    }
                    data["interactions"].append(interaction)
        
        data["contractAddress"] = contract_address
        data["blockRange"] = {
            "fromBlock": from_block,
            "toBlock": to_block
        }
        data["summary"] = {
            "totalLogs": len(data["logs"]),
            "totalTransactions": len(data["transactions"]),
            "totalInteractions": len(data["interactions"])
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def compare_gas_estimates(transaction_object: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run eth_call + eth_estimateGas and compare results.
    
    Args:
        transaction_object: Transaction object with fields like from, to, data, value
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        # Normalize transaction object
        tx_obj = {}
        for key, value in transaction_object.items():
            if key in ["value", "gas", "gasPrice", "nonce"] and isinstance(value, (int, str)):
                if isinstance(value, int):
                    tx_obj[key] = hex(value)
                elif isinstance(value, str) and not value.startswith("0x"):
                    try:
                        tx_obj[key] = hex(int(value))
                    except ValueError:
                        tx_obj[key] = value
                else:
                    tx_obj[key] = value
            else:
                tx_obj[key] = value
        
        # Run eth_call
        call_result = None
        try:
            call_result = await rpc.call("eth_call", [tx_obj, "latest"])
            rpc_calls += 1
        except Exception as e:
            call_result = {"error": str(e)}
        
        # Run eth_estimateGas
        gas_estimate = None
        try:
            gas_estimate = await rpc.call("eth_estimateGas", [tx_obj])
            rpc_calls += 1
        except Exception as e:
            gas_estimate = {"error": str(e)}
        
        data["transactionObject"] = tx_obj
        data["callResult"] = call_result
        data["gasEstimate"] = gas_estimate
        
        if isinstance(gas_estimate, str):
            gas_estimate_int = hex_to_int(gas_estimate)
            data["gasEstimateWei"] = gas_estimate_int
            data["gasEstimateGwei"] = gas_estimate_int / 1e9
        
        # Comparison
        if call_result and isinstance(gas_estimate, str):
            data["comparison"] = {
                "callSucceeded": not isinstance(call_result, dict) or "error" not in call_result,
                "gasEstimateAvailable": True,
                "estimatedGas": hex_to_int(gas_estimate)
            }
        else:
            data["comparison"] = {
                "callSucceeded": False,
                "gasEstimateAvailable": False,
                "errors": {
                    "call": call_result.get("error") if isinstance(call_result, dict) else None,
                    "estimateGas": gas_estimate.get("error") if isinstance(gas_estimate, dict) else None
                }
            }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 2: Hyperliquid-Specific Tools
# ============================================================================

@mcp.tool()
async def get_system_transactions(
    block_range: Dict[str, Union[str, int]]
) -> Dict[str, Any]:
    """
    Fetch system transactions from block range.
    Note: System transactions are identified by specific patterns (e.g., zero-value, specific addresses).
    
    Args:
        block_range: Dict with "fromBlock" and "toBlock"
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {
        "systemTransactions": []
    }
    rpc_calls = 0
    
    try:
        from_block = normalize_block(block_range.get("fromBlock", "0"))
        to_block = normalize_block(block_range.get("toBlock", "latest"))
        
        # Get end block number
        if to_block == "latest":
            latest_block_data = await rpc.call("eth_getBlockByNumber", ["latest", False])
            rpc_calls += 1
            to_block_num = hex_to_int(latest_block_data.get("number", "0x0"))
        else:
            to_block_num = hex_to_int(to_block)
        
        from_block_num = hex_to_int(from_block) if from_block not in ["latest", "earliest", "pending"] else 0
        
        # Limit range
        max_blocks = 100
        if to_block_num - from_block_num > max_blocks:
            to_block_num = from_block_num + max_blocks
        
        # Sample blocks to find system transactions
        # System transactions are typically: zero value, contract creation, or specific patterns
        step = max(1, (to_block_num - from_block_num) // 50)  # Sample up to 50 blocks
        
        for block_num in range(from_block_num, to_block_num + 1, step):
            block_hex = hex(block_num)
            block = await rpc.call("eth_getBlockByNumber", [block_hex, True])
            rpc_calls += 1
            
            if block and "transactions" in block:
                for tx in block["transactions"]:
                    if isinstance(tx, dict):
                        value = hex_to_int(tx.get("value", "0x0"))
                        to_addr = tx.get("to")
                        input_data = tx.get("input", "0x")
                        
                        # Identify system transactions (heuristics)
                        is_system_tx = (
                            value == 0 and len(input_data) > 2  # Zero value with data
                            or to_addr is None  # Contract creation
                            or (input_data != "0x" and len(input_data) > 66)  # Complex contract calls
                        )
                        
                        if is_system_tx:
                            sys_tx = {
                                "hash": tx.get("hash"),
                                "blockNumber": hex_to_int(tx.get("blockNumber", "0x0")),
                                "from": tx.get("from"),
                                "to": tx.get("to"),
                                "value": value,
                                "gas": hex_to_int(tx.get("gas", "0x0")),
                                "gasPrice": hex_to_int(tx.get("gasPrice", "0x0")),
                                "input": input_data,
                                "type": "contract_creation" if to_addr is None else "contract_call"
                            }
                            data["systemTransactions"].append(sys_tx)
        
        data["blockRange"] = {
            "fromBlock": from_block_num,
            "toBlock": to_block_num,
            "blocksScanned": len(range(from_block_num, to_block_num + 1, step))
        }
        data["summary"] = {
            "totalSystemTransactions": len(data["systemTransactions"])
        }
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def analyze_system_tx_patterns(
    block_range: Dict[str, Union[str, int]]
) -> Dict[str, Any]:
    """
    Analyze frequency, types, and gas usage of system transactions.
    
    Args:
        block_range: Dict with "fromBlock" and "toBlock"
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        # First get system transactions
        sys_tx_result = await get_system_transactions(block_range)
        rpc_calls += sys_tx_result["metadata"]["rpc_calls"]
        
        system_txs = sys_tx_result.get("data", {}).get("systemTransactions", [])
        
        if not system_txs:
            data["message"] = "No system transactions found in range"
            data["patterns"] = {}
        else:
            # Analyze patterns
            types = {}
            gas_usage = []
            frequencies = {}
            
            for tx in system_txs:
                tx_type = tx.get("type", "unknown")
                types[tx_type] = types.get(tx_type, 0) + 1
                
                gas = tx.get("gas", 0)
                gas_usage.append(gas)
                
                # Group by from address
                from_addr = tx.get("from", "unknown")
                frequencies[from_addr] = frequencies.get(from_addr, 0) + 1
            
            data["patterns"] = {
                "byType": types,
                "typeDistribution": {
                    k: (v / len(system_txs)) * 100 
                    for k, v in types.items()
                },
                "gasUsage": {
                    "total": sum(gas_usage),
                    "average": sum(gas_usage) / len(gas_usage) if gas_usage else 0,
                    "min": min(gas_usage) if gas_usage else 0,
                    "max": max(gas_usage) if gas_usage else 0
                },
                "topAddresses": dict(sorted(frequencies.items(), key=lambda x: x[1], reverse=True)[:10]),
                "totalTransactions": len(system_txs)
            }
            
            data["summary"] = {
                "totalSystemTxs": len(system_txs),
                "uniqueTypes": len(types),
                "uniqueAddresses": len(frequencies),
                "avgGasPerTx": data["patterns"]["gasUsage"]["average"]
            }
        
        data["blockRange"] = block_range
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)

