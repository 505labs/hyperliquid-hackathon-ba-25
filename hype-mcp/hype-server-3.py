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
LAVA_RPC_URL = os.getenv("LAVA_RPC_URL")
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

