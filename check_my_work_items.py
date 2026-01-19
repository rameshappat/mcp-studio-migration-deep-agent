#!/usr/bin/env python
"""Check work items using the correct tool name."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_work_items():
    """Check existing work items."""
    
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
        # Try to get "my work items" (recently created/assigned)
        result = await client.call_tool('wit_my_work_items', {})
        
        print(f"\nResult: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(check_work_items())
