#!/usr/bin/env python3
"""Quick verification that cleanup is complete."""

import asyncio
from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def verify():
    """Verify cleanup status."""
    print("\n" + "="*60)
    print("🧹 CLEANUP VERIFICATION")
    print("="*60)
    
    client = AzureDevOpsMCPClient(organization="appatr", project="testingmcp")
    await client.connect()
    
    # Check work items
    print("\n📋 Checking work items...")
    try:
        results = await client.call_tool("wit_query_by_wiql", {
            "project": "testingmcp",
            "wiql": "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = 'testingmcp'"
        })
        work_items = results.get("workItems", [])
        print(f"   Total work items: {len(work_items)}")
        
        if work_items:
            print("\n   Remaining work items:")
            for wi in work_items:
                wi_id = wi.get("id")
                print(f"   - ID {wi_id}")
    except Exception as e:
        print(f"   ⚠️  Error checking work items: {e}")
    
    # Check test plans
    print("\n📊 Checking test plans...")
    try:
        plans = await client.call_tool("testplan_list_test_plans", {
            "project": "testingmcp"
        })
        plan_list = plans.get("value", [])
        print(f"   Total test plans: {len(plan_list)}")
        
        if plan_list:
            print("\n   Test plans found:")
            for plan in plan_list:
                print(f"   - ID {plan.get('id')}: {plan.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   ⚠️  Error checking test plans: {e}")
    
    print("\n" + "="*60)
    print("✅ VERIFICATION COMPLETE")
    print("="*60 + "\n")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(verify())
