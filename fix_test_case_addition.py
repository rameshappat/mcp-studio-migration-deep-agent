#!/usr/bin/env python
"""Fix test case addition with correct parameters."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def fix_test_cases():
    """Add test cases 1163-1167 to suite 370 with CORRECT parameters."""
    
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("FIXING TEST CASE ADDITION TO SUITE")
    print("=" * 60)
    
    test_case_ids = [1163, 1164, 1165, 1166, 1167]
    
    for tc_id in test_case_ids:
        print(f"\nAdding test case {tc_id} to suite 370...")
        
        try:
            # Use correct parameter names and STRING test case ID!
            result = await client.call_tool('testplan_add_test_cases_to_suite', {
                'project': 'testingmcp',
                'planId': 369,  # camelCase!
                'suiteId': 370,  # camelCase!
                'testCaseIds': str(tc_id)  # STRING!
            })
            
            print(f"   Result: {result}")
            
            if isinstance(result, dict) and 'text' in result and 'error' in result['text'].lower():
                print(f"   ❌ FAILED")
            else:
                print(f"   ✅ SUCCESS")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    # Verify by listing
    print(f"\n{'='*60}")
    print("VERIFYING TEST CASES IN SUITE 370")
    print("=" * 60)
    
    try:
        result = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': 369,  # lowercase for list!
            'suiteid': 370   # lowercase for list!
        })
        
        print(f"\nTest cases in suite: {len(result) if isinstance(result, list) else 0}")
        for idx, tc in enumerate(result if isinstance(result, list) else [], 1):
            print(f"{idx}. {tc}")
            
    except Exception as e:
        print(f"ERROR: {e}")
    
    await client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(fix_test_cases())
