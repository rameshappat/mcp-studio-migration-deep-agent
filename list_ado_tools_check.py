"""List available ADO MCP tools."""
import asyncio
from src.studio_graph_autonomous import get_ado_client


async def list_tools():
    client = get_ado_client()
    
    # Check available tools (hack - look at internal state)
    print("Checking available tools...")
    
    # Try calling a known tool
    result = await client.call_tool('wit_get_work_item', {
        'workItemId': 1250
    }, timeout=30)
    
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(list_tools())
