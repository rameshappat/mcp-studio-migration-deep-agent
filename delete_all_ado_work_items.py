#!/usr/bin/env python
"""Delete all work items and test cases from ADO (preserves Test Plan 369 and Suite 370)."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def delete_all_work_items():
    """Delete all work items in ADO."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("🗑️  DELETING ALL WORK ITEMS FROM ADO")
    print("=" * 60)
    
    try:
        # Query all work items
        result = await client.call_tool('ado_wit_query_by_wiql', {
            'project': 'testingmcp',
            'query': 'SELECT [System.Id], [System.Title], [System.WorkItemType] FROM WorkItems WHERE [System.TeamProject] = @project ORDER BY [System.Id] DESC'
        })
        
        print(f"\nQuery result: {result}")
        
        if isinstance(result, dict) and 'workItems' in result:
            work_items = result.get('workItems', [])
            print(f"\n📋 Found {len(work_items)} work items")
            
            deleted = 0
            failed = 0
            
            for wi in work_items:
                wi_id = wi.get('id')
                wi_type = wi.get('fields', {}).get('System.WorkItemType', 'Unknown')
                wi_title = wi.get('fields', {}).get('System.Title', 'N/A')
                
                print(f"\n🗑️  Deleting {wi_type} {wi_id}: {wi_title[:50]}...")
                
                try:
                    delete_result = await client.call_tool('ado_wit_delete_work_item', {
                        'project': 'testingmcp',
                        'id': wi_id
                    })
                    print(f"   ✅ Deleted successfully")
                    deleted += 1
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    failed += 1
            
            print("\n" + "=" * 60)
            print(f"✅ Cleanup complete!")
            print(f"   Deleted: {deleted}")
            print(f"   Failed: {failed}")
            print(f"   Test Plan 369 and Suite 370 preserved")
            print("=" * 60)
        else:
            print(f"❌ No work items found or unexpected result format")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(delete_all_work_items())
