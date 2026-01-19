#!/usr/bin/env python3
"""Test the direct test case creation to verify it works."""

import sys
import os
import asyncio
sys.path.insert(0, 'src')

from mcp_client.ado_client import AzureDevOpsMCPClient


async def test_direct_creation():
    """Test direct test case creation without Deep Agent."""
    
    org = os.getenv("AZURE_DEVOPS_ORG", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    print(f"\n=== Testing Direct Test Case Creation ===")
    print(f"Organization: {org}")
    print(f"Project: {project}\n")
    
    client = AzureDevOpsMCPClient(organization=org, project=project)
    await client.connect()
    
    print("✅ Connected to ADO MCP\n")
    
    # Test creating ONE test case
    print("1. Creating test case...")
    result = await client.call_tool('testplan_create_test_case', {
        'project': project,
        'title': 'Test: Direct Creation Verification',
        'steps': '1. Open application|App loads\n2. Click button|Button works\n3. Verify result|Success shown',
        'priority': 2
    }, timeout=60)
    
    if isinstance(result, dict) and "error" in result:
        print(f"   ❌ FAILED: {result.get('text', 'Unknown error')}")
        print("\n   Trying REST API fallback...")
        # REST fallback will be automatic
    elif result.get("id"):
        test_case_id = result["id"]
        print(f"   ✅ Created test case: {test_case_id}")
        
        # Test adding to suite
        print(f"\n2. Adding to suite 370...")
        result2 = await client.call_tool('testplan_add_test_cases_to_suite', {
            'project': project,
            'planId': 369,
            'suiteId': 370,
            'testCaseIds': str(test_case_id)
        }, timeout=60)
        
        if isinstance(result2, dict) and "error" in result2:
            print(f"   ❌ FAILED: {result2.get('text', 'Unknown error')}")
        else:
            print(f"   ✅ Added to suite successfully")
            print(f"\n✅ TEST PASSED - Test case {test_case_id} created and added to suite!")
    else:
        print(f"   ⚠️  Unexpected result: {result}")
    
    await client.close()
    print("\n")


if __name__ == "__main__":
    asyncio.run(test_direct_creation())
