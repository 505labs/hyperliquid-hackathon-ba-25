Jakob fir, [16 Nov 2025 at 15:00:26]:
# Hyperliquid Hackathon Project

[Demo Video](https://youtu.be/M3nPyOhwMM0)

The problem with the hyperliquid is that even with existing block explorer most of the interesting analytics are hard to use, because they involve a lot of blockchain knowledge and processing. This is why we're introducing a comprehensive MCP (Model Context Protocol) server implementation for analyzing and interacting with the Hyperliquid blockchain using Lava Network's high-performance RPC API endpoints.

## Overview

This project provides a suite of tools for developers and users to gain visibility into Hyperliquid's onchain activity. It includes multiple MCP server implementations offering different tiers of functionality, from basic RPC wrappers to advanced compound actions and agent-friendly workflows.

## Project Structure
hyperliquid-hackathon-ba-25/
├── hype-mcp/                    # Main MCP server implementation
│   ├── hype-server-1.py        # Tier 1: Direct RPC API wrappers
│   ├── hype-server-2.py        # Tier 2: Compound action tools
│   ├── vault-server.py         # Vault-specific analysis tools
│   ├── hyperliquid_log_processor.py  # Log processing utilities
│   ├── hyperliquid-python-sdk/ # Hyperliquid Python SDK
│   └── README.md               # Detailed MCP server documentation
├── tasks/                       # Hackathon task specifications
│   ├── lava.md                 # Lava Network task (this project)
│   ├── gluex.md
│   ├── hypurrfi.md
│   └── looping-collective.md
└── README.md                   # This file
...## Features

### Tier 1 Tools (hype-server-1.py)
Direct API wrappers for Hyperliquid chain analysis:
- Chain & Network: Get chain info, check sync status
- Blocks: Get blocks by number/hash, extract transactions
- Transactions: Get transaction details, receipts, gas estimation
- Accounts: Query balances, nonces, contract code, storage
- Calls & Execution: Contract calls, event log queries
- Gas & Fees: Gas price, fee history

### Tier 2 Tools (hype-server-2.py)
Compound actions that combine multiple RPC calls:
- Transaction management and monitoring
- Account analysis and tracking
- Block analysis with transaction details
- Log filtering and event processing

### Vault Tools (vault-server.py)
Specialized tools for Hyperliquid vault analysis:
- List vault addresses
- Get vault deposit/withdrawal activity
- Analyze vault performance metrics

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Navigate to the MCP server directory:
cd hype-mcp
...2. Install dependencies:
uv sync
...3. (Optional) Set environment variables:
export LAVA_RPC_URL="https://your-lava-rpc-endpoint"
export HYPERLIQUID_NETWORK="mainnet"  # or "testnet"
...If LAVA_RPC_URL is not set, the server will use a default Lava endpoint. For production use, configure your own endpoint from [Lava Network](https://accounts.lavanet.xyz/).

### Running the Server

Run the Tier 1 server:
uv run mcp-server hype-mcp.hype-server-1 stdio
...Run the Tier 2 server:
uv run mcp-server hype-mcp.hype-server-2 stdio
...For development/testing with the MCP Inspector:
uv run mcp-inspector hype-mcp.hype-server-1
...## Documentation

- [MCP Server README](./hype-mcp/README.md) - Comprehensive documentation for the MCP server, including all available tools, usage examples, and testing instructions
- [Vault Server Guide](./hype-mcp/VAULT_SERVER.md) - Documentation for vault-specific analysis tools
- [Demo Tools](./hype-mcp/DEMO_TOOLS.md) - Examples and demos for Tier 3 agent-friendly workflows
- [Debug Guide](./hype-mcp/DEBUG_GUIDE.md) - Troubleshooting and debugging tips

## Testing

The project includes comprehensive integration tests that use actual Lava RPC endpoints:
# Install test dependencies
uv sync --extra test

# Run all tests
uv run pytest

# Run specific test suites
uv run pytest test_tier2.py
uv run pytest test_vault_server.py
...See the [MCP Server README](./hype-mcp/README.md) for detailed testing instructions.

## Hackathon Context


This project was built for the HyperEVM Hackathon as part of the Lava Network bounty. The goal was to build a developer or user-facing tool that enriches onchain visibility into Hyperliquid using Lava Network's high-performance RPC API endpoints.

### Task Requirements
- ✅ Fetch data from the Lava RPC API for Hyperliquid
- ✅ Implement a usable interface (MCP server for AI agents)
- ✅ Display information in real-time (via MCP tools)

## Technical Stack

- Python 3.13+ - Core language
- FastMCP - MCP server framework
- httpx - Async HTTP client for RPC calls
- Hyperliquid Python SDK - Native SDK integration
- Lava Network RPC - High-performance blockchain RPC endpoints

## Response Format

All tools return standardized responses:
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
...## Contributing

This is a hackathon submission. For questions or improvements, please open an issue or pull request.

## License

MIT