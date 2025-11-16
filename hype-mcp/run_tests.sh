#!/bin/bash
# Simple test runner script for MCP tools

echo "Running MCP Tools Tests..."
echo "=========================="
echo ""

# Install test dependencies if needed
if ! uv pip list | grep -q pytest; then
    echo "Installing test dependencies..."
    uv sync --extra test
fi

# Run tests
echo "Running Tier 2 tests..."
uv run pytest test_tier2.py -v

echo ""
echo "Running Tier 3 (Demo) tests..."
uv run pytest test_tier3.py -v

echo ""
echo "All tests completed!"

