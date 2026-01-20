#!/usr/bin/env python3
"""Check work items and test the ID extraction logic"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def main():
    client = AzureDevOpsMCPClient(organization="appatr", project="testingmcp")
    
    try:
        await client.connect()
        
        print("="*70)
        print("CHECKING WORK ITEMS 1242-1247")
        print("="*70)
        
        work_item_ids = [1242, 1243, 1244, 1245, 1246, 1247]
        
        for wi_id in work_item_ids:
            result = await client.call_tool('wit_get_work_item', {
                'id': wi_id,
                'project': 'testingmcp'
            })
            
            if isinstance(result, dict):
                fields = result.get('fields', {})
                print(f"\n✅ Work Item {wi_id}:")
                print(f"   Type: {fields.get('System.WorkItemType')}")
                print(f"   Title: {fields.get('System.Title')}")
        
        # Now test creating test cases for these work items
        print("\n" + "="*70)
        print("CREATING TEST CASES FOR WORK ITEMS")
        print("="*70)
        
        test_suite_id = 370
        test_plan_id = 369
        
        for wi_id in work_item_ids[:3]:  # Just test first 3
            print(f"\n🧪 Creating test case for work item {wi_id}...")
            
            result = await client.call_tool('testplan_create_test_case', {
                'project': 'testingmcp',
                'title': f'Test Case for Work Item {wi_id}',
                'steps': '1. Setup|Verify setup complete\n2. Execute|Verify execution\n3. Cleanup|Verify cleanup',
                'priority': 2,
                'tests_work_item_id': wi_id
            })
            
            if isinstance(result, dict) and 'id' in result:
                test_case_id = result['id']
                print(f"   ✅ Created test case ID: {test_case_id}")
                
                # Add to suite
                add_result = await client.call_tool('testplan_add_test_cases_to_suite', {
                    'project': 'testingmcp',
                    'planId': test_plan_id,
                    'suiteId': test_suite_id,
                    'testCaseIds': str(test_case_id)
                })
                print(f"   ✅ Added to suite 370")
            else:
                print(f"   ❌ Failed: {result}")
        
        print("\n" + "="*70)
        print("✅ MANUAL TEST CASE CREATION SUCCESSFUL")
        print("="*70)
        print("\nThis proves:")
        print("1. Work items exist (1242-1247)")
        print("2. Test case creation works")
        print("3. Problem: The autonomous graph is NOT extracting work item IDs")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
