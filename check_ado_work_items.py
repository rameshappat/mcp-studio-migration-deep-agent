#!/usr/bin/env python
"""Check what work items currently exist in ADO."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_work_items():
    """Check work items in ADO."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("CHECKING WORK ITEMS IN ADO")
    print("=" * 60)
    
    try:
        # List work items using WIQL query
        result = await client.call_tool('ado_wit_query_by_wiql', {
            'project': 'testingmcp',
            'query': 'SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType] FROM WorkItems WHERE [System.TeamProject] = @project ORDER BY [System.Id] DESC'
        })
        
        print(f"\nQuery result type: {type(result)}")
        print(f"\nRaw result: {result}")
        
        if isinstance(result, dict):
            work_items = result.get('workItems', [])
            print(f"\n✅ Found {len(work_items)} work items:")
            for idx, wi in enumerate(work_items[:20], 1):  # Show first 20
                print(f"{idx}. ID: {wi.get('id')}, Type: {wi.get('fields', {}).get('System.WorkItemType')}, Title: {wi.get('fields', {}).get('System.Title', 'N/A')}")
        else:
            print(f"Unexpected result format: {result}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(check_work_items())
