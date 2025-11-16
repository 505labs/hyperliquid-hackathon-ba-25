"""
Test suite for Tier 2 MCP tools.
Integration tests using actual Lava RPC endpoints.
"""

import pytest
import asyncio
import os
import sys
from typing import Dict, Any, List

# Add the parent directory to path to import the server module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the server module
# Note: Python doesn't allow hyphens in module names, so we use importlib
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hype_server_2",
    os.path.join(os.path.dirname(__file__), "hype-server-2.py")
)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

# Get RPC URL from environment or use default from server module
RPC_URL = os.getenv("LAVA_RPC_URL") or server_module.LAVA_RPC_URL
SKIP_IF_NO_RPC = os.getenv("SKIP_IF_NO_RPC", "false").lower() == "true"


@pytest.fixture(autouse=True)
async def setup_rpc_client():
    """Setup and teardown RPC client for each test."""
    # Reset global state
    server_module._rpc_client = None
    server_module._cache.clear()
    
    # Set RPC URL
    original_url = server_module.LAVA_RPC_URL
    server_module.LAVA_RPC_URL = RPC_URL
    
    yield
    
    # Cleanup
    if server_module._rpc_client:
        try:
            await server_module._rpc_client.close()
        except:
            pass
    server_module._rpc_client = None
    server_module._cache.clear()
    server_module.LAVA_RPC_URL = original_url


@pytest.fixture
async def rpc_client():
    """Get actual RPC client."""
    return await server_module.get_rpc_client()


@pytest.fixture
async def latest_block_info(rpc_client):
    """Get latest block information for tests."""
    try:
        block = await rpc_client.call("eth_getBlockByNumber", ["latest", False])
        block_num = int(block.get("number", "0x0"), 16) if block else 0
        return {
            "number": block_num,
            "hex": hex(block_num),
            "block": block
        }
    except Exception as e:
        pytest.skip(f"Could not get latest block: {e}")


@pytest.fixture
async def test_transaction_hash(rpc_client, latest_block_info):
    """Get a real transaction hash from recent blocks for testing."""
    try:
        # Get a recent block with transactions
        for i in range(5):
            block_num = latest_block_info["number"] - i
            if block_num < 0:
                break
            block = await rpc_client.call("eth_getBlockByNumber", [hex(block_num), True])
            if block and block.get("transactions"):
                tx = block["transactions"][0]
                if isinstance(tx, dict):
                    return tx.get("hash")
        pytest.skip("No transactions found in recent blocks")
    except Exception as e:
        pytest.skip(f"Could not get test transaction: {e}")


@pytest.fixture
async def test_address(rpc_client, test_transaction_hash):
    """Get a real address from a transaction for testing."""
    try:
        tx = await rpc_client.call("eth_getTransactionByHash", [test_transaction_hash])
        if tx:
            return tx.get("from") or tx.get("to")
        pytest.skip("Could not get address from transaction")
    except Exception as e:
        pytest.skip(f"Could not get test address: {e}")


# ============================================================================
# Transaction Management Tests
# ============================================================================

@pytest.mark.asyncio
async def test_wait_for_transaction_confirmation_success(rpc_client, test_transaction_hash, latest_block_info):
    """Test waiting for transaction confirmation with a real transaction."""
    # Use a real transaction hash that's already confirmed
    tx_hash = test_transaction_hash
    
    result = await server_module.wait_for_transaction_confirmation(
        tx_hash, confirmations=1, timeout=30
    )
    
    assert result["success"] is True
    assert result["data"]["status"] in ["confirmed", "pending"]
    if result["data"]["status"] == "confirmed":
        assert "receipt" in result["data"]
        assert result["data"]["confirmations"] >= 0


@pytest.mark.asyncio
async def test_wait_for_transaction_confirmation_invalid_hash(rpc_client):
    """Test waiting for confirmation with invalid transaction hash."""
    # Use a fake transaction hash
    tx_hash = "0x" + "0" * 64
    
    result = await server_module.wait_for_transaction_confirmation(
        tx_hash, confirmations=1, timeout=5
    )
    
    # Should timeout or return pending status
    assert result["data"]["status"] in ["timeout", "pending"]


@pytest.mark.asyncio
async def test_track_transaction_status(rpc_client, test_transaction_hash):
    """Test tracking transaction status through lifecycle with real transaction."""
    tx_hash = test_transaction_hash
    
    result = await server_module.track_transaction_status(tx_hash, poll_interval=0.5)
    
    assert result["success"] is True
    assert "history" in result["data"]
    assert len(result["data"]["history"]) > 0
    assert result["data"]["finalStatus"] in ["pending", "mined", "confirmed"]


@pytest.mark.asyncio
async def test_get_transaction_cost_analysis(rpc_client, test_transaction_hash):
    """Test transaction cost analysis with real transaction."""
    tx_hash = test_transaction_hash
    
    result = await server_module.get_transaction_cost_analysis(tx_hash)
    
    assert result["success"] is True
    assert "totalGasCostWei" in result["data"]
    assert "totalGasCostEth" in result["data"]
    assert "estimatedCostUSD" in result["data"]
    assert "gasUsed" in result["data"]
    assert result["data"]["gasUsed"] > 0


# ============================================================================
# Account Analysis Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_account_activity(rpc_client, test_address, latest_block_info):
    """Test getting account activity in block range with real address."""
    address = test_address
    # Use a small recent block range
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 10)  # Last 10 blocks
    
    result = await server_module.get_account_activity(
        address, start_block=start_block, end_block=end_block
    )
    
    assert result["success"] is True
    assert "transactions" in result["data"]
    assert "sent" in result["data"]
    assert "received" in result["data"]
    assert "blockRange" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.asyncio
async def test_analyze_account_holdings(rpc_client, test_address):
    """Test analyzing account holdings with real address."""
    address = test_address
    
    result = await server_module.analyze_account_holdings(address)
    
    assert result["success"] is True
    assert "balanceWei" in result["data"]
    assert "balanceEth" in result["data"]
    assert "nonceDecimal" in result["data"]
    assert "isContract" in result["data"]
    assert isinstance(result["data"]["isContract"], bool)
    assert "recentTransactionCount" in result["data"]


@pytest.mark.asyncio
async def test_track_balance_changes(rpc_client, test_address, latest_block_info):
    """Test tracking balance changes across blocks with real address."""
    address = test_address
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 5)  # Last 5 blocks
    
    result = await server_module.track_balance_changes(
        address,
        block_range={"start": start_block, "end": end_block, "step": 1}
    )
    
    assert result["success"] is True
    assert "snapshots" in result["data"]
    assert len(result["data"]["snapshots"]) > 0
    assert "blockRange" in result["data"]
    if len(result["data"]["snapshots"]) > 1:
        assert "balanceChange" in result["data"]


# ============================================================================
# Block Analytics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_block_range(rpc_client, latest_block_info):
    """Test getting a range of blocks with real data."""
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 3)  # Last 3 blocks
    
    result = await server_module.get_block_range(
        start_block=start_block, end_block=end_block, full_tx=False
    )
    
    assert result["success"] is True
    assert "blocks" in result["data"]
    assert len(result["data"]["blocks"]) > 0
    assert "range" in result["data"]
    assert result["data"]["range"]["count"] > 0


@pytest.mark.asyncio
async def test_analyze_gas_trends(rpc_client):
    """Test analyzing gas trends from fee history with real data."""
    result = await server_module.analyze_gas_trends(
        block_count=10, percentiles=[25, 50, 75]
    )
    
    assert result["success"] is True
    # Fee history might be empty or have data
    if result["data"]:
        if "baseFeeStats" in result["data"]:
            assert "min" in result["data"]["baseFeeStats"]
            assert "max" in result["data"]["baseFeeStats"]
        if "gasUsedRatioStats" in result["data"]:
            assert "avg" in result["data"]["gasUsedRatioStats"]


@pytest.mark.asyncio
async def test_get_network_health(rpc_client):
    """Test getting network health status with real data."""
    print("\n[TEST] Starting network health check...")
    print(f"[TEST] Using RPC URL: {RPC_URL}")
    
    result = await server_module.get_network_health()
    
    print(f"[TEST] Result success: {result['success']}")
    print(f"[TEST] RPC calls made: {result['metadata']['rpc_calls']}")
    print(f"[TEST] Execution time: {result['metadata']['execution_time']:.2f}ms")
    
    if result["success"]:
        print(f"[TEST] Health status: {result['data'].get('healthStatus')}")
        print(f"[TEST] Gas price: {result['data'].get('gasPrice', {}).get('gwei')} gwei")
        print(f"[TEST] Latest block: {result['data'].get('latestBlock', {}).get('number')}")
    
    assert result["success"] is True
    assert "syncStatus" in result["data"]
    assert "latestBlock" in result["data"]
    assert "gasPrice" in result["data"]
    assert "gasTrend" in result["data"]
    assert "healthStatus" in result["data"]
    assert result["data"]["healthStatus"] in ["healthy", "degraded"]
    
    print("[TEST] All assertions passed!")


# ============================================================================
# Smart Contract Tools Tests
# ============================================================================

@pytest.mark.asyncio
async def test_decode_contract_events(rpc_client, latest_block_info):
    """Test decoding contract events with real data."""
    # Use a known contract address or get one from recent transactions
    # For this test, we'll use a small block range and see if there are any events
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 10)
    
    # Try to find a contract address from recent blocks
    contract_address = None
    try:
        for i in range(5):
            block_num = end_block - i
            if block_num < 0:
                break
            block = await rpc_client.call("eth_getBlockByNumber", [hex(block_num), True])
            if block and block.get("transactions"):
                for tx in block["transactions"]:
                    if isinstance(tx, dict) and tx.get("to"):
                        contract_address = tx.get("to")
                        break
            if contract_address:
                break
    except:
        pass
    
    if not contract_address:
        pytest.skip("No contract address found in recent blocks")
    
    event_signatures = ["Transfer(address,address,uint256)"]
    
    result = await server_module.decode_contract_events(
        contract_address,
        event_signatures,
        block_range={"fromBlock": hex(start_block), "toBlock": hex(end_block)}
    )
    
    assert result["success"] is True
    assert "events" in result["data"]
    assert "bySignature" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.asyncio
async def test_analyze_contract_activity(rpc_client, latest_block_info):
    """Test analyzing contract activity with real data."""
    # Try to find a contract address from recent blocks
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 10)
    
    contract_address = None
    try:
        for i in range(5):
            block_num = end_block - i
            if block_num < 0:
                break
            block = await rpc_client.call("eth_getBlockByNumber", [hex(block_num), True])
            if block and block.get("transactions"):
                for tx in block["transactions"]:
                    if isinstance(tx, dict) and tx.get("to"):
                        contract_address = tx.get("to")
                        break
            if contract_address:
                break
    except:
        pass
    
    if not contract_address:
        pytest.skip("No contract address found in recent blocks")
    
    result = await server_module.analyze_contract_activity(
        contract_address,
        block_range={"fromBlock": hex(start_block), "toBlock": hex(end_block)}
    )
    
    assert result["success"] is True
    assert "interactions" in result["data"]
    assert "transactions" in result["data"]
    assert "logs" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.asyncio
async def test_compare_gas_estimates(rpc_client, test_address):
    """Test comparing gas estimates with real transaction object."""
    # Create a simple transaction object
    tx_obj = {
        "from": test_address,
        "to": test_address,  # Self-transfer
        "data": "0x",
        "value": "0x0"
    }
    
    result = await server_module.compare_gas_estimates(tx_obj)
    
    assert result["success"] is True
    assert "callResult" in result["data"]
    assert "gasEstimate" in result["data"]
    assert "comparison" in result["data"]


# ============================================================================
# Hyperliquid-Specific Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_system_transactions(rpc_client, latest_block_info):
    """Test getting system transactions with real data."""
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 5)  # Last 5 blocks
    
    result = await server_module.get_system_transactions(
        block_range={"fromBlock": hex(start_block), "toBlock": hex(end_block)}
    )
    
    assert result["success"] is True
    assert "systemTransactions" in result["data"]
    assert "blockRange" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.asyncio
async def test_analyze_system_tx_patterns(rpc_client, latest_block_info):
    """Test analyzing system transaction patterns with real data."""
    end_block = latest_block_info["number"]
    start_block = max(0, end_block - 5)  # Last 5 blocks
    
    result = await server_module.analyze_system_tx_patterns(
        block_range={"fromBlock": hex(start_block), "toBlock": hex(end_block)}
    )
    
    assert result["success"] is True
    assert "patterns" in result["data"] or "message" in result["data"]
    if "patterns" in result["data"]:
        assert "byType" in result["data"]["patterns"]
        assert "gasUsage" in result["data"]["patterns"]


# ============================================================================
# Helper Function Tests
# ============================================================================

def test_normalize_block():
    """Test block normalization."""
    assert server_module.normalize_block("0x100") == "0x100"
    assert server_module.normalize_block("100") == hex(100)
    assert server_module.normalize_block(100) == hex(100)
    assert server_module.normalize_block("latest") == "latest"


def test_normalize_address():
    """Test address normalization."""
    assert server_module.normalize_address("0xabc") == "0xabc"
    assert server_module.normalize_address("abc") == "0xabc"


def test_hex_to_int():
    """Test hex to int conversion."""
    assert server_module.hex_to_int("0x100") == 256
    assert server_module.hex_to_int("100") == 100
    assert server_module.hex_to_int(100) == 100


def test_format_response():
    """Test response formatting."""
    response = server_module.format_response(
        {"test": "data"},
        rpc_calls=5,
        execution_time_ms=100.5,
        cached=False,
        errors=None
    )
    
    assert response["success"] is True
    assert response["data"]["test"] == "data"
    assert response["metadata"]["rpc_calls"] == 5
    assert response["metadata"]["execution_time"] == 100.5
    assert response["errors"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
