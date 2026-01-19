#!/usr/bin/env python
"""List all test plans and their test cases."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def list_all_test_plans():
    """List all test plans."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("ALL TEST PLANS IN PROJECT")
    print("=" * 60)
    
    try:
        result = await client.call_tool('testplan_list_test_plans', {
            'project': 'testingmcp'
        })
        
        print(f"\nResult: {result}")
        
        if isinstance(result, dict):
            plans = result.get('value', [])
            print(f"\n✅ Found {len(plans)} test plan(s):")
            for idx, plan in enumerate(plans, 1):
                print(f"\n{idx}. Plan ID: {plan.get('id')}")
                print(f"   Name: {plan.get('name')}")
                print(f"   State: {plan.get('state')}")
                print(f"   Root Suite ID: {plan.get('rootSuite', {}).get('id')}")
        
        # Now try listing test suites for plan 369
        print(f"\n{'='*60}")
        print("TEST SUITES IN PLAN 369")
        print("=" * 60)
        
        suites_result = await client.call_tool('testplan_list_test_suites', {
            'project': 'testingmcp',
            'planId': 369
        })
        
        print(f"\nSuites Result: {suites_result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(list_all_test_plans())
