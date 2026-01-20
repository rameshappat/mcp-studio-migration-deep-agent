#!/usr/bin/env python
"""Check test cases in ADO test suite."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_test_cases():
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    await client.connect()
    
    print("=" * 60)
    print("TEST CASES STATUS")
    print("=" * 60)
    
    # Check test cases in suite 370
    print("\n📝 Test Cases in Suite 370:")
    try:
        result = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': 369,
            'suiteid': 370
        })
        
        print(f"  Result type: {type(result)}")
        if isinstance(result, list):
            if result:
                print(f"  ✅ Found {len(result)} test case(s)\n")
                for idx, test_case in enumerate(result, 1):
                    # The structure has workItem nested
                    work_item = test_case.get('workItem', {})
                    tc_id = work_item.get('id', 'N/A')
                    tc_name = work_item.get('name', 'Unnamed')
                    print(f"    {idx}. Test Case ID: {tc_id}")
                    print(f"       Name: {tc_name}")
            else:
                print(f"  ⚠️  No test cases found in suite 370")
        else:
            print(f"  Result: {result}")
    except Exception as e:
        print(f"  ❌ Error listing test cases: {e}")
        import traceback
        traceback.print_exc()
    
    await client.close()
    
    print("\n" + "=" * 60)
    print("CHECK COMPLETE")
    print("=" * 60)

asyncio.run(check_test_cases())
