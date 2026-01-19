#!/usr/bin/env python3
"""Test MCP timeout -> REST fallback."""

import sys
import os
import asyncio
sys.path.insert(0, 'src')

from mcp_client.ado_client import AzureDevOpsMCPClient


async def test_timeout_fallback():
    """Test that MCP timeout triggers REST fallback."""
    
    org = os.getenv("AZURE_DEVOPS_ORG", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    print(f"\n=== Testing MCP Timeout -> REST Fallback ===")
    print(f"Organization: {org}")
    print(f"Project: {project}\n")
    
    client = AzureDevOpsMCPClient(organization=org, project=project)
    await client.connect()
    
    print("Connected to MCP server\n")
    
    # Test with very short timeout to force fallback
    print("🔄 Calling testplan_list_test_cases with 2s timeout (should trigger fallback)...")
    
    result = await client.call_tool('testplan_list_test_cases', {
        'project': project,
        'planid': 369,
        'suiteid': 370
    }, timeout=2)  # Very short timeout
    
    if isinstance(result, list):
        print(f"✅ SUCCESS: Got {len(result)} test cases")
        for tc in result[:3]:
            wi = tc.get('workItem', {})
            print(f"   • ID {wi.get('id')}: {wi.get('name', 'No name')}")
    elif isinstance(result, dict) and 'error' in result:
        print(f"⚠️ Got error response: {result.get('text', 'Unknown')}")
        print("   This is expected if MCP timed out but REST fallback also failed")
    else:
        print(f"⚠️ Unexpected response type: {type(result)}")
    
    await client.close()
    print("\n✅ Test complete\n")


if __name__ == "__main__":
    asyncio.run(test_timeout_fallback())
