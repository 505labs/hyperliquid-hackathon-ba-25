#!/usr/bin/env python3
"""
Simple RPC test script to verify Lava RPC connectivity and methods.
Tests basic RPC calls as defined in the server files.
"""

import os
import sys
import asyncio
import httpx
from typing import Any, List

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads variables from .env file
    print("✓ Loaded .env file")
except ImportError:
    print("⚠ python-dotenv not installed - .env file won't be loaded")
    print("  Install with: uv add python-dotenv")
    print("  Or set environment variables directly")

# Configuration
LAVA_RPC_URL = os.getenv("LAVA_RPC_URL")

print(f"LAVA_RPC_URL: {LAVA_RPC_URL if LAVA_RPC_URL else 'Not set (using default)'}")

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


def hex_to_int(hex_str: str) -> int:
    """Convert hex string to integer."""
    if isinstance(hex_str, str):
        return int(hex_str, 16) if hex_str.startswith("0x") else int(hex_str)
    return hex_str


async def find_block_with_transactions(rpc: RPCClient, max_blocks_to_check: int = 10) -> dict:
    """
    Find a block that contains transactions and return the first transaction.
    
    Args:
        rpc: RPCClient instance
        max_blocks_to_check: Maximum number of recent blocks to check (default: 10)
    
    Returns:
        Dictionary with block info and first transaction, or None if not found
    """
    print("\n" + "=" * 60)
    print("Finding Block with Transactions")
    print("=" * 60)
    
    try:
        # Get latest block number
        latest_block_hex = await rpc.call("eth_blockNumber")
        latest_block = hex_to_int(latest_block_hex)
        print(f"Latest block: {latest_block}")
        print(f"Checking last {max_blocks_to_check} blocks...")
        
        # Check recent blocks for transactions
        for i in range(max_blocks_to_check):
            block_num = latest_block - i
            if block_num < 0:
                break
            
            try:
                print(f"  Checking block {block_num}...", end=" ", flush=True)
                block = await rpc.call("eth_getBlockByNumber", [hex(block_num), True])
                
                if block and "transactions" in block:
                    tx_count = len(block["transactions"])
                    if tx_count > 0:
                        print(f"✓ Found {tx_count} transactions")
                        
                        # Get first transaction
                        first_tx = block["transactions"][0]
                        
                        if isinstance(first_tx, dict):
                            # Format transaction data
                            tx_data = {
                                "hash": first_tx.get("hash", "N/A"),
                                "blockNumber": hex_to_int(first_tx.get("blockNumber", "0x0")),
                                "blockHash": first_tx.get("blockHash", "N/A"),
                                "from": first_tx.get("from", "N/A"),
                                "to": first_tx.get("to", "N/A"),
                                "value": hex_to_int(first_tx.get("value", "0x0")),
                                "valueEth": hex_to_int(first_tx.get("value", "0x0")) / 1e18,
                                "gas": hex_to_int(first_tx.get("gas", "0x0")),
                                "gasPrice": hex_to_int(first_tx.get("gasPrice", "0x0")),
                                "gasPriceGwei": hex_to_int(first_tx.get("gasPrice", "0x0")) / 1e9,
                                "nonce": hex_to_int(first_tx.get("nonce", "0x0")),
                                "input": first_tx.get("input", "0x"),
                                "transactionIndex": hex_to_int(first_tx.get("transactionIndex", "0x0")),
                            }
                            
                            result = {
                                "block": {
                                    "number": block_num,
                                    "hash": block.get("hash", "N/A"),
                                    "timestamp": hex_to_int(block.get("timestamp", "0x0")),
                                    "transactionCount": tx_count,
                                    "gasUsed": hex_to_int(block.get("gasUsed", "0x0")),
                                    "gasLimit": hex_to_int(block.get("gasLimit", "0x0")),
                                },
                                "firstTransaction": tx_data
                            }
                            
                            # Print formatted output
                            print("\n" + "-" * 60)
                            print("BLOCK INFORMATION")
                            print("-" * 60)
                            print(f"Block Number: {result['block']['number']}")
                            print(f"Block Hash: {result['block']['hash']}")
                            print(f"Timestamp: {result['block']['timestamp']}")
                            print(f"Total Transactions: {result['block']['transactionCount']}")
                            print(f"Gas Used: {result['block']['gasUsed']:,}")
                            print(f"Gas Limit: {result['block']['gasLimit']:,}")
                            
                            print("\n" + "-" * 60)
                            print("FIRST TRANSACTION")
                            print("-" * 60)
                            print(f"Hash: {tx_data['hash']}")
                            print(f"Block Number: {tx_data['blockNumber']}")
                            print(f"From: {tx_data['from']}")
                            print(f"To: {tx_data['to']}")
                            print(f"Value: {tx_data['valueEth']:.6f} ETH ({tx_data['value']:,} wei)")
                            print(f"Gas: {tx_data['gas']:,}")
                            print(f"Gas Price: {tx_data['gasPriceGwei']:.2f} gwei ({tx_data['gasPrice']:,} wei)")
                            print(f"Nonce: {tx_data['nonce']}")
                            print(f"Transaction Index: {tx_data['transactionIndex']}")
                            print(f"Input Data Length: {len(tx_data['input']) - 2} bytes" if tx_data['input'] != "0x" else "Input Data: None")
                            if tx_data['input'] != "0x" and len(tx_data['input']) > 2:
                                print(f"Input Data (first 66 chars): {tx_data['input'][:66]}...")
                            
                            print("=" * 60)
                            return result
                        else:
                            print(f"⚠ Transaction is not a dict: {type(first_tx)}")
                else:
                    print("No transactions")
                    
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        print(f"\n❌ No blocks with transactions found in last {max_blocks_to_check} blocks")
        return None
        
    except Exception as e:
        print(f"\n❌ Error finding block: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_rpc_methods():
    """Test various RPC methods."""
    print("=" * 60)
    print("Lava RPC Connection Test")
    print("=" * 60)
    print(f"RPC URL: {LAVA_RPC_URL}")
    print()
    
    rpc = RPCClient(LAVA_RPC_URL)
    
    tests = [
        ("eth_chainId", [], "Get Chain ID"),
        ("net_version", [], "Get Network Version"),
        ("web3_clientVersion", [], "Get Client Version"),
        ("eth_syncing", [], "Check Sync Status"),
        ("eth_blockNumber", [], "Get Latest Block Number"),
        ("eth_gasPrice", [], "Get Current Gas Price"),
        ("eth_getBlockByNumber", ["latest", False], "Get Latest Block (without transactions)"),
    ]
    
    results = []
    
    for method, params, description in tests:
        try:
            print(f"Testing: {description}")
            print(f"  Method: {method}")
            print(f"  Params: {params}")
            
            result = await rpc.call(method, params)
            
            # Format result for display
            if method == "eth_blockNumber":
                block_num = hex_to_int(result)
                print(f"  Result: {result} (decimal: {block_num})")
            elif method == "eth_gasPrice":
                gas_price = hex_to_int(result)
                gas_price_gwei = gas_price / 1e9
                print(f"  Result: {result} (decimal: {gas_price} wei, {gas_price_gwei:.2f} gwei)")
            elif method == "eth_chainId":
                chain_id = hex_to_int(result)
                print(f"  Result: {result} (decimal: {chain_id})")
            elif method == "eth_syncing":
                if isinstance(result, bool):
                    print(f"  Result: {result} (Synced: {not result})")
                else:
                    print(f"  Result: Syncing - {result}")
            elif method == "eth_getBlockByNumber":
                if result:
                    block_num = hex_to_int(result.get("number", "0x0"))
                    tx_count = len(result.get("transactions", []))
                    print(f"  Result: Block #{block_num} with {tx_count} transactions")
                else:
                    print(f"  Result: None")
            else:
                print(f"  Result: {result}")
            
            results.append((description, "✅ PASSED", None))
            print()
            
        except Exception as e:
            print(f"  ❌ FAILED: {str(e)}")
            results.append((description, "❌ FAILED", str(e)))
            print()
    
    # Test with a real address if available
    test_address = "0x0000000000000000000000000000000000000000"  # Zero address for testing
    try:
        print("Testing: Get Balance")
        print(f"  Method: eth_getBalance")
        print(f"  Address: {test_address}")
        
        balance = await rpc.call("eth_getBalance", [test_address, "latest"])
        balance_wei = hex_to_int(balance)
        balance_eth = balance_wei / 1e18
        print(f"  Result: {balance} (decimal: {balance_wei} wei, {balance_eth} ETH)")
        
        results.append(("Get Balance", "✅ PASSED", None))
        print()
    except Exception as e:
        print(f"  ❌ FAILED: {str(e)}")
        results.append(("Get Balance", "❌ FAILED", str(e)))
        print()
    
    # Test finding a block with transactions using dedicated method
    print("=" * 60)
    print("Testing: Find Block with Transactions")
    print("=" * 60)
    try:
        block_result = await find_block_with_transactions(rpc, max_blocks_to_check=50)
        
        if block_result:
            results.append(("Find Block with Transactions", "✅ PASSED", None))
        else:
            results.append(("Find Block with Transactions", "⚠ NO TRANSACTIONS", "No blocks with transactions found"))
        print()
    except Exception as e:
        print(f"  ❌ FAILED: {str(e)}")
        results.append(("Find Block with Transactions", "❌ FAILED", str(e)))
        print()
    
    await rpc.close()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, status, _ in results if "PASSED" in status)
    failed = sum(1 for _, status, _ in results if "FAILED" in status)
    
    for description, status, error in results:
        print(f"{status} - {description}")
        if error:
            print(f"    Error: {error}")
    
    print()
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(test_rpc_methods())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

