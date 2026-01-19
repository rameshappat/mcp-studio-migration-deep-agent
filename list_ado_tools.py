#!/usr/bin/env python
"""List all available ADO tools."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def list_ado_tools():
    """List all ADO tools."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    tools = client.get_tools()
    
    print(f"\n{'='*60}")
    print(f"AVAILABLE ADO TOOLS ({len(tools)} total)")
    print(f"{'='*60}\n")
    
    # Group by prefix
    work_items = [t for t in tools if 'work' in t['name'].lower() or 'wit' in t['name'].lower()]
    test_plans = [t for t in tools if 'test' in t['name'].lower()]
    others = [t for t in tools if t not in work_items and t not in test_plans]
    
    print(f"WORK ITEM TOOLS ({len(work_items)}):")
    for tool in sorted(work_items, key=lambda x: x['name']):
        print(f"  - {tool['name']}")
    
    print(f"\nTEST PLAN TOOLS ({len(test_plans)}):")
    for tool in sorted(test_plans, key=lambda x: x['name']):
        print(f"  - {tool['name']}")
    
    print(f"\nOTHER TOOLS ({len(others)}):")
    for tool in sorted(others, key=lambda x: x['name']):
        print(f"  - {tool['name']}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(list_ado_tools())
