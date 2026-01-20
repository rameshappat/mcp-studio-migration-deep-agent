"""Debug work item creation."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def debug_create_work_item():
    """Check what wit_create_work_item returns."""
    from src.studio_graph_autonomous import get_ado_client
    
    ado_client = get_ado_client()
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    print("Creating work item...")
    result = await ado_client.call_tool('wit_create_work_item', {
        'project': project,
        'type': 'Issue',
        'title': 'Test Work Item',
        'description': 'Testing work item creation',
    }, timeout=30)
    
    print(f"\nResult type: {type(result)}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
    print(f"Result content:\n{result}")
    
    # Check for ID
    if isinstance(result, dict):
        print(f"\nID field: {result.get('id')}")
        print(f"Text field: {result.get('text', '')[:200]}")


if __name__ == "__main__":
    asyncio.run(debug_create_work_item())
