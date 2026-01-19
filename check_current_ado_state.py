#!/usr/bin/env python3
"""Check current ADO state for test cases."""

import sys
import asyncio
sys.path.insert(0, 'src')

from mcp_client.ado_client import ADOClient


async def main():
    """Check ADO state."""
    client = ADOClient()
    await client.connect()
    
    print("\n=== Checking ADO Test Plans ===\n")
    
    # Get all test plans
    plans = await client.call_tool('testplan_list_test_plans', {'project': 'testingmcp'})
    print(f"📋 Total Test Plans: {len(plans) if plans else 0}")
    
    if plans and isinstance(plans, list):
        for plan in plans:
            plan_id = plan.get('id')
            plan_name = plan.get('name')
            print(f"\n  Plan {plan_id}: {plan_name}")
            
            # Get suites
            suites = await client.call_tool('testplan_list_test_suites', {
                'project': 'testingmcp',
                'planId': plan_id
            })
            
            if suites and isinstance(suites, list):
                print(f"  └─ Suites: {len(suites)}")
                
                for suite in suites[:5]:  # First 5 suites
                    suite_id = suite.get('id')
                    suite_name = suite.get('name')
                    print(f"     Suite {suite_id}: {suite_name}")
                    
                    # Get test cases
                    cases = await client.call_tool('testplan_list_test_cases', {
                        'project': 'testingmcp',
                        'planid': plan_id,
                        'suiteid': suite_id
                    })
                    
                    case_count = len(cases) if cases else 0
                    print(f"        └─ Test Cases: {case_count}")
                    
                    if cases:
                        for case in cases[:3]:
                            work_item = case.get('workItem', {})
                            case_id = work_item.get('id')
                            case_name = work_item.get('name', 'Unnamed')
                            print(f"           • {case_id}: {case_name}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
