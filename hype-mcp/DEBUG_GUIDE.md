# Debug Guide - Viewing Print Statements in MCP Tools

When running MCP servers with stdio transport, **stdout is reserved for the MCP protocol**, so print statements must go to **stderr** to be visible.

## Quick Solution

The code now includes:
1. **`debug_print()` function** - Prints to stderr (safe for MCP)
2. **Python logging** - Configured to use stderr

## Using debug_print()

Instead of `print()`, use `debug_print()`:

```python
debug_print("This will be visible in stderr!")
debug_print(f"Processing block {block_num}")
```

## Using Logger

For more structured logging:

```python
logger.info("Information message")
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message")
```

## Viewing Output

### Method 1: Run Server Directly (See stderr)

```bash
# Run server and see stderr output
uv run python -m mcp.server.fastmcp hype-mcp.hype-server-3 stdio 2>&1 | tee server.log
```

### Method 2: Use MCP Inspector (Recommended for Development)

The MCP Inspector shows logs in its interface:

```bash
uv run mcp-inspector hype-mcp.hype-server-3
```

Then call tools through the inspector - logs will appear in the inspector's console.

### Method 3: Redirect stderr to File

```bash
# Run server and save stderr to file
uv run mcp-server hype-mcp.hype-server-3 stdio 2> debug.log

# In another terminal, watch the log file
tail -f debug.log
```

### Method 4: Run with Python Directly (For Testing)

For quick testing/debugging, you can run the module directly:

```python
# test_debug.py
import asyncio
import sys
sys.path.insert(0, '.')

from hype_server_3 import get_top_profitable_traders

async def test():
    result = await get_top_profitable_traders(hours=1, top_n=3)
    print(result)

asyncio.run(test())
```

Then run:
```bash
uv run python test_debug.py
```

## Example: Adding Debug to Your Tools

```python
@mcp.tool()
async def my_tool(param: str) -> Dict[str, Any]:
    debug_print(f"[my_tool] Called with param={param}")
    logger.info(f"Processing tool call: {param}")
    
    try:
        # Your code here
        debug_print(f"[my_tool] Step 1: Doing something...")
        result = await some_operation()
        debug_print(f"[my_tool] Step 1 complete: {result}")
        
        return format_response({"result": result})
    except Exception as e:
        logger.error(f"[my_tool] Error: {e}", exc_info=True)
        raise
```

## Important Notes

1. **Never use `print()` directly** - It goes to stdout and breaks MCP protocol
2. **Always use `debug_print()` or `logger`** - They use stderr
3. **Flush is automatic** - `debug_print()` includes `flush=True`
4. **Logging levels** - Set via `logging.basicConfig(level=...)`:
   - `logging.DEBUG` - All messages
   - `logging.INFO` - Info and above
   - `logging.WARNING` - Warnings and errors only

## Testing Print Statements

To test if your prints are working:

```bash
# This should show your debug output
uv run python -c "
import sys
sys.path.insert(0, '.')
from hype_server_3 import debug_print
debug_print('Test message - you should see this!')
"
```

You should see: `Test message - you should see this!`

