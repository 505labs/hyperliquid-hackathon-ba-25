# How to See Print Statements in Tests

## Problem
Pytest captures stdout/stderr by default, so print statements are hidden unless a test fails.

## Solutions

### Solution 1: Use `-s` flag (Recommended)

Run tests with the `-s` flag to disable output capture:

```bash
# Run all tests with output visible
uv run pytest -s

# Run specific test file
uv run pytest test_tier2.py -s

# Run specific test
uv run pytest test_tier2.py::test_get_account_activity -s -v
```

### Solution 2: Use `-v -s` for verbose output

```bash
uv run pytest -v -s test_tier2.py
```

### Solution 3: Use `--capture=no` (same as -s)

```bash
uv run pytest --capture=no test_tier2.py
```

### Solution 4: Use `pytest.ini` configuration

The `pytest.ini` file now includes `-s` in `addopts`, so print statements should be visible by default.

If you still don't see output, run:
```bash
uv run pytest -s -v
```

## Print Statements in Server Code

If you're using `print()` in your server code (hype-server-*.py), remember:

1. **Use `debug_print()`** - Goes to stderr (safe for MCP)
2. **Use `logger.info()`** - Structured logging to stderr
3. **Never use `print()` directly** - It goes to stdout and breaks MCP protocol

## Example: Adding Debug to Tests

```python
@pytest.mark.asyncio
async def test_my_function(rpc_client):
    print("This will be visible with -s flag")
    print(f"Testing with RPC: {rpc_client.url}")
    
    result = await some_function()
    
    print(f"Result: {result}")
    assert result["success"] is True
```

## Running Tests with Full Output

```bash
# See all output including prints
uv run pytest -s -v test_tier2.py

# See output and stop on first failure
uv run pytest -s -v -x test_tier2.py

# See output with detailed traceback
uv run pytest -s -v --tb=long test_tier2.py
```

## Quick Reference

| Flag | Description |
|------|-------------|
| `-s` | Disable output capture (show prints) |
| `-v` | Verbose output |
| `-vv` | Very verbose |
| `-x` | Stop on first failure |
| `--tb=short` | Short traceback format |
| `--tb=long` | Long traceback format |
| `--capture=no` | Same as `-s` |

