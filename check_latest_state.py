#!/usr/bin/env python3
"""Check what actually happened in the last run"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def main():
    client = AzureDevOpsMCPClient(
        organization="appatr",
        project="testingmcp"
    )
    
    try:
        await client.connect()
        
        print("\n" + "="*70)
        print("CHECKING CURRENT ADO STATE")
        print("="*70)
        
        # Get all work items
        print("\n1. WORK ITEMS:")
        result = await client.call_tool('wit_query_wiql', {
            'project': 'testingmcp',
            'wiql': 'SELECT [System.Id], [System.Title], [System.WorkItemType], [System.CreatedDate] FROM workitems WHERE [System.TeamProject] = @project ORDER BY [System.CreatedDate] DESC'
        })
        
        if isinstance(result, dict):
            work_items = result.get('workItems', [])
            print(f"   Total: {len(work_items)} work items")
            
            if work_items:
                print("\n   Most recent 10:")
                for wi in work_items[:10]:
                    wi_id = wi.get('id')
                    wi_details = await client.call_tool('wit_get_work_item', {
                        'id': wi_id,
                        'project': 'testingmcp'
                    })
                    
                    if isinstance(wi_details, dict):
                        fields = wi_details.get('fields', {})
                        print(f"   - ID {wi_id}: {fields.get('System.WorkItemType')} - {fields.get('System.Title', 'N/A')[:60]}")
        
        # Check test cases
        print("\n2. TEST CASES IN SUITE 370:")
        test_cases = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': 369,
            'suiteid': 370
        })
        
        if isinstance(test_cases, list):
            print(f"   Total: {len(test_cases)} test cases")
            if test_cases:
                for tc in test_cases[:5]:
                    if isinstance(tc, dict):
                        wi = tc.get('workItem', {})
                        print(f"   - Test Case {wi.get('id')}: {wi.get('name', 'N/A')}")
        else:
            print(f"   None found")
        
        print("\n" + "="*70)
        print("DIAGNOSIS:")
        print("="*70)
        
        work_item_count = len(work_items) if isinstance(result, dict) else 0
        test_case_count = len(test_cases) if isinstance(test_cases, list) else 0
        
        if work_item_count > 0 and test_case_count == 0:
            print("\n❌ PROBLEM: Work items exist but no test cases!")
            print("   This means:")
            print("   1. Work items were created")
            print("   2. BUT their IDs were NOT captured")
            print("   3. test_plan_agent_node ran with empty created_ids list")
            print("\n   Check the LangGraph logs for:")
            print("   - '📋 WORK ITEMS AGENT - RETURNING STATE'")
            print("   - '🔍 TEST PLAN AGENT NODE - DEBUGGING STATE'")
        elif work_item_count == 0:
            print("\n⚠️  No work items found - pipeline may not have run yet")
        else:
            print(f"\n✅ Found {work_item_count} work items and {test_case_count} test cases")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
