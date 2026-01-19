#!/usr/bin/env python
"""Verify test cases are in the test suite."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_suite_test_cases():
    """Check test cases in suite 370."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("TEST SUITE 370 - TEST CASES")
    print("=" * 60)
    
    try:
        result = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': 369,
            'suiteid': 370
        })
        
        print(f"\nResult: {result}")
        
        if isinstance(result, dict):
            test_cases = result.get('value', [])
            print(f"\n✅ Found {len(test_cases)} test case(s) in suite 370:")
            for idx, tc in enumerate(test_cases, 1):
                tc_fields = tc.get('workItem', {}).get('fields', {})
                print(f"\n{idx}. Test Case ID: {tc.get('workItem', {}).get('id')}")
                print(f"   Title: {tc_fields.get('System.Title', 'N/A')}")
                print(f"   State: {tc_fields.get('System.State', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(check_suite_test_cases())
