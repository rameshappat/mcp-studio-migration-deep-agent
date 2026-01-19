#!/usr/bin/env python
"""Debug why test cases aren't showing in the suite."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def debug_suite_addition():
    """Debug the test case addition to suite."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("DEBUGGING TEST CASE ADDITION")
    print("=" * 60)
    
    # Test case 1163 exists, let's try to add it to suite 370
    test_case_id = 1163
    test_plan_id = 369
    test_suite_id = 370
    
    print(f"\nAttempting to add test case {test_case_id} to suite {test_suite_id}...")
    
    try:
        result = await client.call_tool('testplan_add_test_cases_to_suite', {
            'project': 'testingmcp',
            'test_plan_id': test_plan_id,
            'test_suite_id': test_suite_id,
            'test_case_ids': [test_case_id]
        })
        
        print(f"\n✅ Result from add_test_cases_to_suite:")
        print(f"   Type: {type(result)}")
        print(f"   Content: {result}")
        
    except Exception as e:
        print(f"\n❌ ERROR during add_test_cases_to_suite:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
    
    # Now let's try listing with different parameter combinations
    print(f"\n{'='*60}")
    print("TRYING TO LIST TEST CASES WITH DIFFERENT PARAMETERS")
    print("=" * 60)
    
    # Try 1: planid, suiteid
    try:
        result1 = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': test_plan_id,
            'suiteid': test_suite_id
        })
        print(f"\n1. With planid/suiteid: {result1}")
    except Exception as e:
        print(f"\n1. With planid/suiteid - ERROR: {e}")
    
    # Try 2: planId, suiteId
    try:
        result2 = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planId': test_plan_id,
            'suiteId': test_suite_id
        })
        print(f"\n2. With planId/suiteId: {result2}")
    except Exception as e:
        print(f"\n2. With planId/suiteId - ERROR: {e}")
    
    # Try 3: Check the tool schema
    print(f"\n{'='*60}")
    print("CHECKING TOOL SCHEMA")
    print("=" * 60)
    
    tools = client.get_tools()
    for tool in tools:
        if 'test' in tool['name'].lower() and 'case' in tool['name'].lower():
            print(f"\nTool: {tool['name']}")
            print(f"Schema: {tool.get('inputSchema', {})}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(debug_suite_addition())
