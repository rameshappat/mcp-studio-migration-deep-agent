#!/usr/bin/env python3
"""Check current ADO work items and test cases."""

from src.mcp_client.ado_client import AzureDevOpsMCPClient
import asyncio

async def check_ado():
    """Check ADO work items and test cases."""
    print("\n" + "="*60)
    print("🔍 CHECKING ADO STATE")
    print("="*60)
    
    client = AzureDevOpsMCPClient(organization="appatr", project="testingmcp")
    await client.connect()
    
    # Get all work items
    print("\n📋 Checking work items...")
    wiql = "SELECT [System.Id], [System.WorkItemType], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = 'testingmcp' ORDER BY [System.Id] DESC"
    results = await client.call_tool("wit_query_by_wiql", {
        "project": "testingmcp",
        "wiql": wiql
    })
    
    work_items = results.get("workItems", [])
    print(f"   Total work items: {len(work_items)}")
    
    if work_items:
        print("\n   Recent work items:")
        for wi in work_items[:10]:  # Show last 10
            wi_id = wi.get("id")
            # Get details
            details = await client.call_tool("wit_get_work_item_by_id", {
                "project": "testingmcp",
                "id": wi_id
            })
            wi_type = details.get("fields", {}).get("System.WorkItemType", "Unknown")
            title = details.get("fields", {}).get("System.Title", "No title")
            state = details.get("fields", {}).get("System.State", "Unknown")
            print(f"   - ID {wi_id}: [{wi_type}] {title} ({state})")
    
    # Check test plan 369
    print("\n📊 Checking Test Plan 369...")
    try:
        plan_info = await client.call_tool("testplan_get_test_plan", {
            "project": "testingmcp",
            "planid": 369
        })
        print(f"   Plan: {plan_info.get('name', 'Unknown')}")
        
        # Check suite 370
        print("\n📦 Checking Test Suite 370...")
        test_cases = await client.call_tool("testplan_list_test_cases", {
            "project": "testingmcp",
            "planid": 369,
            "suiteid": 370
        })
        
        if isinstance(test_cases, list):
            print(f"   Test cases in suite: {len(test_cases)}")
            if test_cases:
                print("\n   Test cases:")
                for tc in test_cases:
                    tc_id = tc.get("workItem", {}).get("id", "Unknown")
                    tc_name = tc.get("workItem", {}).get("name", "No name")
                    print(f"   - TC {tc_id}: {tc_name}")
            else:
                print("   ❌ NO TEST CASES IN SUITE!")
        else:
            print(f"   ❌ Unexpected response: {test_cases}")
            
    except Exception as e:
        print(f"   ❌ Error checking test plan: {e}")
    
    print("\n" + "="*60)
    await client.close()

if __name__ == "__main__":
    asyncio.run(check_ado())
