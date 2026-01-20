"""Debug get_work_item response."""
import asyncio
from src.studio_graph_autonomous import get_ado_client


async def debug():
    client = get_ado_client()
    
    # Try getting work item 1250
    print("Fetching work item 1250...")
    result = await client.get_work_item(work_item_id=1250)
    
    print(f"\nResult type: {type(result)}")
    print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
    print(f"\nFull result:")
    import json
    print(json.dumps(result, indent=2)[:1000])


if __name__ == "__main__":
    asyncio.run(debug())
