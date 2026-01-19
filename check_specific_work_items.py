#!/usr/bin/env python
"""Get details of specific work items to check if test cases exist."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_work_items():
    """Check work items 1163-1167."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("CHECKING WORK ITEMS 1163-1167")
    print("=" * 60)
    
    try:
        result = await client.call_tool('wit_get_work_items_batch_by_ids', {
            'ids': [1163, 1164, 1165, 1166, 1167]
        })
        
        if isinstance(result, dict):
            work_items = result.get('value', [])
            print(f"\n✅ Found {len(work_items)} work items:")
            for wi in work_items:
                fields = wi.get('fields', {})
                print(f"\nID: {wi.get('id')}")
                print(f"  Type: {fields.get('System.WorkItemType', 'N/A')}")
                print(f"  Title: {fields.get('System.Title', 'N/A')}")
                print(f"  State: {fields.get('System.State', 'N/A')}")
        else:
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(check_work_items())
