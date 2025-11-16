"""
Hyperliquid Lava RPC MCP Server - Tier 1
Provides fundamental blockchain RPC tools and Hyperliquid-specific information endpoints.

This server offers:
- Basic Ethereum-compatible RPC calls (blocks, transactions, accounts, gas, logs)
- Direct Hyperliquid protocol information (orders, fills, portfolio, staking, etc.)
- Use this server for: single-operation queries, getting raw blockchain data, accessing Hyperliquid user/asset information

For compound operations that combine multiple RPC calls, use the Tier 2 server instead.
"""

import os
import time
from typing import Any, Dict, List, Optional, Union

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads variables from .env file
    print("✓ Loaded .env file")
except ImportError:
    print("⚠ python-dotenv not installed - .env file won't be loaded")
    print("  Install with: uv add python-dotenv")
    print("  Or set environment variables directly")

import httpx
from mcp.server.fastmcp import FastMCP
from hyperliquid_log_processor import CoreWriterLogProcessor
from hyperliquid import info
# Create an MCP server
mcp = FastMCP(
    "Hyperliquid Lava RPC - Tier 1",
    description="Fundamental blockchain RPC tools and Hyperliquid protocol information. Use for single-operation queries, raw blockchain data, and Hyperliquid user/asset information."
)

# Configuration
LAVA_RPC_URL = os.getenv("LAVA_RPC_URL", "https://eth1.lava.build/lava-referer-8b51600b-b188-4c52-8c57-c65d3a9be5af/")
NETWORK = os.getenv("HYPERLIQUID_NETWORK", "mainnet")  # mainnet or testnet


# Simple cache for chainId and gasPrice
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


# ============================================================================
# Tier 1: Chain & Network Tools
# ============================================================================

@mcp.tool()
async def get_chain_info() -> Dict[str, Any]:
    """
    Get comprehensive chain metadata including chain ID, network version, client version, and sync status.
    
    Use this tool when you need to:
    - Verify which network you're connected to (mainnet/testnet)
    - Check if the node is fully synced
    - Get basic network information for validation
    
    Returns: chainId, netVersion, clientVersion, syncing status
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 0
    
    try:
        # Check cache for chainId
        cache_key = "chainId"
        if cache_key in _cache:
            cached_value, cache_time = _cache[cache_key]
            if time.time() - cache_time < CACHE_TTL:
                data["chainId"] = cached_value
                rpc_calls = 0
            else:
                del _cache[cache_key]
        
        if "chainId" not in data:
            chain_id = await rpc.call("eth_chainId")
            data["chainId"] = chain_id
            _cache[cache_key] = (chain_id, time.time())
            rpc_calls += 1
        
        # Get other info
        net_version = await rpc.call("net_version")
        data["netVersion"] = net_version
        rpc_calls += 1
        
        client_version = await rpc.call("web3_clientVersion")
        data["clientVersion"] = client_version
        rpc_calls += 1
        
        syncing = await rpc.call("eth_syncing")
        data["syncing"] = syncing
        rpc_calls += 1
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def check_node_sync_status() -> Dict[str, Any]:
    """
    Check if the RPC node is fully synced with the blockchain.
    
    Use this tool when you need to:
    - Verify data freshness before making queries
    - Check if the node is catching up after downtime
    - Validate that you're getting the latest blockchain state
    
    Returns: isSynced boolean, isSyncing boolean, and progress details if syncing
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        syncing = await rpc.call("eth_syncing")
        
        if isinstance(syncing, bool):
            data["isSyncing"] = syncing
            data["isSynced"] = not syncing
            data["progress"] = None
        else:
            # syncing is an object with progress info
            data["isSyncing"] = True
            data["isSynced"] = False
            data["progress"] = syncing
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 1: Blocks Tools
# ============================================================================

@mcp.tool()
async def get_block(block_id: str, full_transactions: bool = False) -> Dict[str, Any]:
    """
    Get a single block by number, hash, or special identifier.
    
    Use this tool when you need to:
    - Inspect a specific block's contents
    - Get block metadata (timestamp, gas used, transaction count)
    - Retrieve transactions from a known block
    
    Args:
        block_id: Block number (hex/decimal), block hash, or "latest"/"earliest"/"pending"
        full_transactions: If True, returns full transaction objects; if False, only transaction hashes
    
    For multiple blocks, use Tier 2 server's get_block_range tool instead.
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        # Normalize block_id
        if isinstance(block_id, str):
            if block_id.startswith("0x"):
                # It's a hash or hex number
                block_param = block_id
            elif block_id in ["latest", "earliest", "pending"]:
                block_param = block_id
            else:
                # Try to convert decimal to hex
                try:
                    block_num = int(block_id)
                    block_param = hex(block_num)
                except ValueError:
                    block_param = block_id
        else:
            # Assume it's a number
            block_param = hex(int(block_id))
        
        block = await rpc.call("eth_getBlockByNumber", [block_param, full_transactions])
        data = block if block else {}
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_latest_block(full_transactions: bool = False) -> Dict[str, Any]:
    """
    Get the most recently mined block on the chain.
    
    Use this tool when you need to:
    - Get the current block number
    - Check the latest block timestamp
    - See recent transactions
    
    Args:
        full_transactions: If True, includes full transaction objects; if False, only transaction hashes
    """
    return await get_block("latest", full_transactions)


@mcp.tool()
async def get_block_transactions(block_id: str) -> Dict[str, Any]:
    """
    Extract transactions array from a block.
    
    Args:
        block_id: Block number (hex string or decimal) or block hash, or "latest", "earliest", "pending"
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {"transactions": []}
    rpc_calls = 1
    
    try:
        # Normalize block_id
        if isinstance(block_id, str):
            if block_id.startswith("0x"):
                block_param = block_id
            elif block_id in ["latest", "earliest", "pending"]:
                block_param = block_id
            else:
                try:
                    block_num = int(block_id)
                    block_param = hex(block_num)
                except ValueError:
                    block_param = block_id
        else:
            block_param = hex(int(block_id))
        
        block = await rpc.call("eth_getBlockByNumber", [block_param, True])
        
        if block and "transactions" in block:
            data["transactions"] = block["transactions"]
            data["blockNumber"] = block.get("number")
            data["blockHash"] = block.get("hash")
            data["transactionCount"] = len(block["transactions"])
        else:
            data["transactions"] = []
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 1: Transactions Tools
# ============================================================================

@mcp.tool()
async def get_transaction(tx_hash: str) -> Dict[str, Any]:
    """
    Get a transaction's details by its hash.
    
    Use this tool when you need to:
    - Inspect a specific transaction's parameters (from, to, value, data)
    - Check transaction status before it's mined
    - Get transaction details for analysis
    
    Args:
        tx_hash: Transaction hash (0x-prefixed hex string)
    
    For transaction receipt (after mining) or cost analysis, use get_transaction_receipt or Tier 2 tools.
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        tx = await rpc.call("eth_getTransactionByHash", [tx_hash])
        data = tx if tx else {}
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_transaction_receipt(tx_hash: str) -> Dict[str, Any]:
    """
    Get a transaction receipt after it has been mined.
    
    Use this tool when you need to:
    - Verify a transaction was successfully executed
    - Get gas used and block number where transaction was mined
    - Check transaction status (success/failure)
    - Get event logs emitted by the transaction
    
    Args:
        tx_hash: Transaction hash (0x-prefixed hex string)
    
    Note: Returns null if transaction hasn't been mined yet. For waiting/monitoring, use Tier 2 server tools.
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        receipt = await rpc.call("eth_getTransactionReceipt", [tx_hash])
        data = receipt if receipt else {}
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def estimate_transaction_gas(transaction_object: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate gas for a transaction.
    
    Args:
        transaction_object: Transaction object with fields like from, to, data, value, gas, gasPrice
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        # Ensure all hex values are properly formatted
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
        
        gas_estimate = await rpc.call("eth_estimateGas", [tx_obj])
        data["gasEstimate"] = gas_estimate
        data["gasEstimateDecimal"] = int(gas_estimate, 16) if isinstance(gas_estimate, str) else gas_estimate
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 1: Accounts Tools
# ============================================================================

@mcp.tool()
async def get_account_balance(address: str, block: str = "latest") -> Dict[str, Any]:
    """
    Get the native token balance of an account at a specific block.
    
    Use this tool when you need to:
    - Check current or historical account balance
    - Verify balance before/after a transaction
    - Get balance at a specific point in time
    
    Args:
        address: Account address (0x-prefixed hex string)
        block: Block number or "latest"/"earliest"/"pending" (default: "latest")
    
    Returns balance in wei (hex and decimal formats).
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not address.startswith("0x"):
            address = "0x" + address
        
        # Normalize block parameter
        if isinstance(block, str) and block not in ["latest", "earliest", "pending"]:
            if not block.startswith("0x"):
                try:
                    block = hex(int(block))
                except ValueError:
                    pass
        
        balance = await rpc.call("eth_getBalance", [address, block])
        data["balance"] = balance
        data["balanceWei"] = int(balance, 16) if isinstance(balance, str) else balance
        data["address"] = address
        data["block"] = block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_account_nonce(address: str, block: str = "latest") -> Dict[str, Any]:
    """
    Get account transaction count (nonce).
    
    Args:
        address: Account address (0x-prefixed hex string)
        block: Block number or "latest", "earliest", "pending" (default: "latest")
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not address.startswith("0x"):
            address = "0x" + address
        
        # Normalize block parameter
        if isinstance(block, str) and block not in ["latest", "earliest", "pending"]:
            if not block.startswith("0x"):
                try:
                    block = hex(int(block))
                except ValueError:
                    pass
        
        nonce = await rpc.call("eth_getTransactionCount", [address, block])
        data["nonce"] = nonce
        data["nonceDecimal"] = int(nonce, 16) if isinstance(nonce, str) else nonce
        data["address"] = address
        data["block"] = block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_contract_code(address: str, block: str = "latest") -> Dict[str, Any]:
    """
    Get contract code at address.
    
    Args:
        address: Contract address (0x-prefixed hex string)
        block: Block number or "latest", "earliest", "pending" (default: "latest")
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not address.startswith("0x"):
            address = "0x" + address
        
        # Normalize block parameter
        if isinstance(block, str) and block not in ["latest", "earliest", "pending"]:
            if not block.startswith("0x"):
                try:
                    block = hex(int(block))
                except ValueError:
                    pass
        
        code = await rpc.call("eth_getCode", [address, block])
        data["code"] = code
        data["hasCode"] = code != "0x" and code != ""
        data["codeLength"] = len(code) - 2 if code.startswith("0x") else len(code)  # Subtract 0x prefix
        data["address"] = address
        data["block"] = block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def get_storage_at(address: str, position: str, block: str = "latest") -> Dict[str, Any]:
    """
    Get storage value at address and position.
    
    Args:
        address: Contract address (0x-prefixed hex string)
        position: Storage position (0x-prefixed hex string or hex number)
        block: Block number or "latest", "earliest", "pending" (default: "latest")
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        if not address.startswith("0x"):
            address = "0x" + address
        
        # Normalize position
        if not position.startswith("0x"):
            try:
                position = hex(int(position))
            except ValueError:
                position = "0x" + position
        
        # Normalize block parameter
        if isinstance(block, str) and block not in ["latest", "earliest", "pending"]:
            if not block.startswith("0x"):
                try:
                    block = hex(int(block))
                except ValueError:
                    pass
        
        storage = await rpc.call("eth_getStorageAt", [address, position, block])
        data["storageValue"] = storage
        data["address"] = address
        data["position"] = position
        data["block"] = block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 1: Calls & Execution Tools
# ============================================================================

@mcp.tool()
async def call_contract(transaction_object: Dict[str, Any], block: str = "latest") -> Dict[str, Any]:
    """
    Call a contract method (eth_call).
    
    Args:
        transaction_object: Transaction object with fields like from, to, data, value
        block: Block number or "latest", "earliest", "pending" (default: "latest")
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        # Ensure all hex values are properly formatted
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
        
        # Normalize block parameter
        if isinstance(block, str) and block not in ["latest", "earliest", "pending"]:
            if not block.startswith("0x"):
                try:
                    block = hex(int(block))
                except ValueError:
                    pass
        
        result = await rpc.call("eth_call", [tx_obj, block])
        data["result"] = result
        data["transactionObject"] = tx_obj
        data["block"] = block
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


@mcp.tool()
async def query_logs(filter_object: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query event logs (eth_getLogs).
    
    Args:
        filter_object: Filter object with fields like fromBlock, toBlock, address, topics
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {"logs": []}
    rpc_calls = 1
    
    try:
        # Normalize block numbers in filter
        filter_obj = {}
        for key, value in filter_object.items():
            if key in ["fromBlock", "toBlock"] and isinstance(value, (int, str)):
                if isinstance(value, int):
                    filter_obj[key] = hex(value)
                elif isinstance(value, str) and value not in ["latest", "earliest", "pending"]:
                    if not value.startswith("0x"):
                        try:
                            filter_obj[key] = hex(int(value))
                        except ValueError:
                            filter_obj[key] = value
                    else:
                        filter_obj[key] = value
                else:
                    filter_obj[key] = value
            else:
                filter_obj[key] = value
        
        logs = await rpc.call("eth_getLogs", [filter_obj])
        data["logs"] = logs if logs else []
        data["logCount"] = len(data["logs"])
        data["filter"] = filter_obj
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)


# ============================================================================
# Tier 1: Gas & Fees Tools
# ============================================================================

@mcp.tool()
async def get_gas_price() -> Dict[str, Any]:
    """
    Get the current network gas price.
    
    Use this tool when you need to:
    - Estimate transaction costs
    - Set gas price for new transactions
    - Check current network congestion
    
    Returns gas price in wei (cached for 60 seconds to reduce RPC calls).
    
    For gas trend analysis over time, use Tier 2 server's analyze_gas_trends tool.
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    cached = False
    
    try:
        # Check cache
        cache_key = "gasPrice"
        if cache_key in _cache:
            cached_value, cache_time = _cache[cache_key]
            if time.time() - cache_time < CACHE_TTL:
                data["gasPrice"] = cached_value
                data["gasPriceWei"] = int(cached_value, 16) if isinstance(cached_value, str) else cached_value
                cached = True
                rpc_calls = 0
            else:
                del _cache[cache_key]
        
        if not cached:
            gas_price = await rpc.call("eth_gasPrice")
            data["gasPrice"] = gas_price
            data["gasPriceWei"] = int(gas_price, 16) if isinstance(gas_price, str) else gas_price
            _cache[cache_key] = (gas_price, time.time())
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=cached, errors=errors if errors else None)


@mcp.tool()
async def get_fee_history(
    block_count: Union[int, str],
    newest_block: str = "latest",
    reward_percentiles: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Get fee history.
    
    Args:
        block_count: Number of blocks to retrieve
        newest_block: Highest number block of the requested range, or "latest", "earliest", "pending"
        reward_percentiles: Optional list of percentile values with a monotonic increase in value
    """
    start_time = time.time()
    rpc = await get_rpc_client()
    errors = []
    data = {}
    rpc_calls = 1
    
    try:
        # Normalize block_count
        if isinstance(block_count, str):
            try:
                block_count = int(block_count)
            except ValueError:
                raise ValueError("block_count must be a number")
        
        # Normalize newest_block
        if isinstance(newest_block, str) and newest_block not in ["latest", "earliest", "pending"]:
            if not newest_block.startswith("0x"):
                try:
                    newest_block = hex(int(newest_block))
                except ValueError:
                    pass
        
        params = [hex(block_count), newest_block]
        if reward_percentiles:
            params.append(reward_percentiles)
        
        fee_history = await rpc.call("eth_feeHistory", params)
        data = fee_history if fee_history else {}
        
    except Exception as e:
        errors.append(str(e))
    
    execution_time = (time.time() - start_time) * 1000
    return format_response(data, rpc_calls, execution_time, cached=False, errors=errors if errors else None)

@mcp.tool()
async def get_core_writer_logs(start_block: int, end_block: int) -> Dict[str, Any]:
    """
    Get CoreWriter logs from start block to end block.
    CoreWriter is the contract that writes the Limit order/Vault transfer/Token delegate/Staking deposit/Staking withdraw/Spot send/USD class transfer/Finalize evm contract/Add api wallet/Cancel order by oid/Cancel order by cloid/Approve builder fee/Send asset/Reflect evm supply change logs.
    """
    start_time = time.time()
    processor = CoreWriterLogProcessor()
    logs = processor.process_logs(start_block, end_block)
    return format_response(logs, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

    # INSERT_YOUR_CODE

# Expose all fundamental info endpoints from info.py
hl_info = info.Info()

@mcp.tool()
async def get_open_orders(address: str, dex: str = "") -> Dict[str, Any]:
    """
    Get all currently open trading orders for a Hyperliquid user.
    
    Use this tool when you need to:
    - Check a user's active orders
    - Monitor order status
    - Get order details (price, size, side, etc.)
    
    Args:
        address: User wallet address
        dex: Optional DEX identifier (empty string for default)
    """
    start_time = time.time()
    result = hl_info.open_orders(address, dex)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_frontend_open_orders(address: str, dex: str = "") -> Dict[str, Any]:
    """
    Get a user's frontend open orders.
    """
    start_time = time.time()
    result = hl_info.frontend_open_orders(address, dex)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_fills(address: str) -> Dict[str, Any]:
    """
    Get all trade fills (executed orders) for a Hyperliquid user.
    
    Use this tool when you need to:
    - View trading history
    - Analyze executed trades
    - Calculate trading performance
    
    Args:
        address: User wallet address
    
    For time-filtered fills, use get_user_fills_by_time instead.
    """
    start_time = time.time()
    result = hl_info.user_fills(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_fills_by_time(address: str, start_time_ms: int, end_time_ms: int = None, aggregate_by_time: bool = False) -> Dict[str, Any]:
    """
    Get a user's fills by time.
    """
    st = time.time()
    result = hl_info.user_fills_by_time(address, start_time_ms, end_time=end_time_ms, aggregate_by_time=aggregate_by_time)
    return format_response(result, 1, (time.time() - st) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_portfolio(address: str) -> Dict[str, Any]:
    """
    Get comprehensive portfolio performance data for a Hyperliquid user.
    
    Use this tool when you need to:
    - View user's trading positions and PnL
    - Analyze portfolio performance
    - Get account equity and margin information
    
    Args:
        address: User wallet address
    """
    start_time = time.time()
    result = hl_info.portfolio(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_clearinghouse_state(address: str, dex: str = "") -> Dict[str, Any]:
    """
    Get a user's clearinghouse state including margin, positions, and account details.
    
    Use this tool when you need to:
    - Check margin requirements and available margin
    - View all open positions
    - Get account health metrics
    
    Args:
        address: User wallet address
        dex: Optional DEX identifier (empty string for default)
    """
    start_time = time.time()
    result = hl_info.user_state(address, dex)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_spot_user_state(address: str) -> Dict[str, Any]:
    """
    Get a user's spot clearinghouse state.
    """
    start_time = time.time()
    result = hl_info.spot_user_state(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_historical_orders(address: str) -> Dict[str, Any]:
    """
    Get a user's historical orders.
    """
    start_time = time.time()
    result = hl_info.historical_orders(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_vault_equities(address: str) -> Dict[str, Any]:
    """
    Get a user's vault equities.
    """
    start_time = time.time()
    result = hl_info.user_vault_equities(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_fees(address: str) -> Dict[str, Any]:
    """
    Get trading volume and fee schedule for a user.
    """
    start_time = time.time()
    result = hl_info.user_fees(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_staking_summary(address: str) -> Dict[str, Any]:
    """
    Get staking summary including total staked amount and rewards for a Hyperliquid user.
    
    Use this tool when you need to:
    - Check user's total staked HYPE
    - View staking rewards
    - Get staking position overview
    
    Args:
        address: User wallet address
    
    For detailed delegation information, use get_user_staking_delegations or the Vault Server.
    """
    start_time = time.time()
    result = hl_info.user_staking_summary(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_staking_delegations(address: str) -> Dict[str, Any]:
    """
    Get staking delegations for a user.
    """
    start_time = time.time()
    result = hl_info.user_staking_delegations(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_staking_rewards(address: str) -> Dict[str, Any]:
    """
    Get historic staking rewards for a user.
    """
    start_time = time.time()
    result = hl_info.user_staking_rewards(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_delegator_summary(address: str) -> Dict[str, Any]:
    """
    Get staking delegator summary for a user.
    """
    start_time = time.time()
    result = hl_info.user_staking_summary(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_delegator_history(address: str) -> Dict[str, Any]:
    """
    Get comprehensive staking history for a user.
    """
    start_time = time.time()
    result = hl_info.delegator_history(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_extra_agents(address: str) -> Dict[str, Any]:
    """
    Get extra agents associated with a user.
    """
    start_time = time.time()
    result = hl_info.extra_agents(address)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_meta(dex: str = "") -> Dict[str, Any]:
    """
    Get perp meta for the dex.
    """
    start_time = time.time()
    result = hl_info.meta(dex)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_meta_and_asset_ctxs() -> Dict[str, Any]:
    """
    Get full meta and asset contexts.
    """
    start_time = time.time()
    result = hl_info.meta_and_asset_ctxs()
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_perp_dexs() -> Dict[str, Any]:
    """
    Get list of perp dexs on Hyperliquid.
    """
    start_time = time.time()
    result = hl_info.perp_dexs()
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_spot_meta() -> Dict[str, Any]:
    """
    Get Hyperliquid spot metadata.
    """
    start_time = time.time()
    result = hl_info.spot_meta()
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_spot_meta_and_asset_ctxs() -> Dict[str, Any]:
    """
    Get Hyperliquid spot meta and asset contexts.
    """
    start_time = time.time()
    result = hl_info.spot_meta_and_asset_ctxs()
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_funding_history(name: str, start_time_ms: int, end_time_ms: int = None) -> Dict[str, Any]:
    """
    Get funding history for a coin.
    """
    start_time = time.time()
    result = hl_info.funding_history(name, start_time_ms, end_time_ms)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_user_funding_history(address: str, start_time_ms: int, end_time_ms: int = None) -> Dict[str, Any]:
    """
    Get funding history for a user.
    """
    start_time = time.time()
    result = hl_info.user_funding_history(address, start_time_ms, end_time_ms)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_l2_snapshot(name: str) -> Dict[str, Any]:
    """
    Get L2 snapshot for a coin.
    """
    start_time = time.time()
    result = hl_info.l2_snapshot(name)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_candles_snapshot(name: str, interval: str, start_time_ms: int, end_time_ms: int) -> Dict[str, Any]:
    """
    Get candles snapshot for a coin.
    """
    start_time = time.time()
    result = hl_info.candles_snapshot(name, interval, start_time_ms, end_time_ms)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

@mcp.tool()
async def get_all_mids(dex: str = "") -> Dict[str, Any]:
    """
    Get all mids for actively traded coins.
    """
    start_time = time.time()
    result = hl_info.all_mids(dex)
    return format_response(result, 1, (time.time() - start_time) * 1000, cached=False, errors=None)

