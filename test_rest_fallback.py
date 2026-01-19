#!/usr/bin/env python3
"""Test REST API fallback for test case operations."""

import sys
import os
import asyncio
sys.path.insert(0, 'src')

from mcp_client.ado_client import AzureDevOpsMCPClient


async def test_rest_fallback():
    """Test REST API fallback."""
    
    org = os.getenv("AZURE_DEVOPS_ORG", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    pat = os.getenv("AZURE_DEVOPS_PAT", "")
    
    if not pat:
        print("❌ Set AZURE_DEVOPS_PAT environment variable")
        return
    
    print(f"\n=== Testing REST API Fallback ===")
    print(f"Organization: {org}")
    print(f"Project: {project}\n")
    
    client = AzureDevOpsMCPClient(organization=org, project=project)
    
    # Don't connect to MCP - go straight to REST
    print("🔄 Testing direct REST API calls...\n")
    
    # Test 1: List test cases
    print("1. Listing test cases in suite 370...")
    result = await client._rest_list_test_cases({
        'project': project,
        'planid': 369,
        'suiteid': 370
    })
    
    if isinstance(result, list):
        print(f"   ✅ Found {len(result)} test cases")
        for tc in result[:3]:
            wi = tc.get('workItem', {})
            print(f"      • ID {wi.get('id')}: {wi.get('name', 'No name')}")
    elif isinstance(result, dict) and 'error' in result:
        print(f"   ❌ Error: {result.get('text', 'Unknown error')}")
    else:
        print(f"   ⚠️ Unexpected result: {type(result)}")
    
    print("\n2. Creating a test case...")
    result = await client._rest_create_test_case({
        'project': project,
        'title': 'Test: REST API Fallback Test Case',
        'steps': '1. Open application|Application loads\\n2. Click test button|Button responds\\n3. Verify result|Expected result appears',
        'priority': 2
    })
    
    if isinstance(result, dict) and result.get('id'):
        test_case_id = result['id']
        print(f"   ✅ Created test case ID: {test_case_id}")
        
        print("\n3. Adding test case to suite 370...")
        result = await client._rest_add_test_cases_to_suite({
            'project': project,
            'planId': 369,
            'suiteId': 370,
            'testCaseIds': [str(test_case_id)]
        })
        
        if isinstance(result, list) and len(result) > 0:
            print(f"   ✅ Added test case {test_case_id} to suite")
        elif isinstance(result, dict) and 'error' in result:
            print(f"   ❌ Error: {result.get('text', 'Unknown error')}")
        else:
            print(f"   ⚠️ Unexpected result: {result}")
    elif isinstance(result, dict) and 'error' in result:
        print(f"   ❌ Error: {result.get('text', 'Unknown error')}")
    else:
        print(f"   ⚠️ Unexpected result: {type(result)}")
    
    print("\n✅ REST API fallback test complete!\n")


if __name__ == "__main__":
    asyncio.run(test_rest_fallback())
