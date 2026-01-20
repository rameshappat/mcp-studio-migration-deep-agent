#!/usr/bin/env python3
"""Direct test - can we create a work item?"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def main():
    client = AzureDevOpsMCPClient(organization="appatr", project="testingmcp")
    
    try:
        await client.connect()
        print("✅ Connected to ADO MCP")
        
        # Try to create ONE work item directly
        print("\n🧪 Testing work item creation...")
        result = await client.call_tool('mcp_ado_wit_create_work_item', {
            'project': 'testingmcp',
            'title': 'TEST: Direct Work Item Creation',
            'workItemType': 'Issue',
            'description': 'This is a test to verify work item creation works',
        })
        
        print(f"\n📋 Result: {result}")
        
        if isinstance(result, dict) and 'id' in result:
            print(f"\n✅ SUCCESS! Created work item ID: {result['id']}")
            print("\n   This means:")
            print("   - MCP connection works")
            print("   - Tool calls work")
            print("   - Problem is in the Deep Agent configuration")
        else:
            print(f"\n❌ FAILED! Result doesn't have 'id': {result}")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
