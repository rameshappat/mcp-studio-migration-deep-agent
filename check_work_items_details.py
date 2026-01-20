#!/usr/bin/env python
"""Check work item details."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_work_items():
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    await client.connect()
    
    print("Checking work items created by autonomous graph:\n")
    
    for wi_id in [1215, 1214, 1213, 1212, 1211, 1210, 1209, 1208]:
        try:
            wi = await client.get_work_item(work_item_id=wi_id)
            fields = wi.get('fields', {})
            
            print(f"WI-{wi_id}:")
            print(f"  Type: {fields.get('System.WorkItemType', 'N/A')}")
            print(f"  Title: {fields.get('System.Title', 'N/A')}")
            print(f"  Description: {fields.get('System.Description', 'N/A')[:100]}...")
            print()
        except Exception as e:
            print(f"WI-{wi_id}: Error - {e}\n")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(check_work_items())
