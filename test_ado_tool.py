#!/usr/bin/env python3
"""Test ADO MCP tool call directly."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_ado_tool():
    """Test calling ADO tool to create a work item."""
    from src.mcp_client.ado_client import AzureDevOpsMCPClient
    
    org = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    print(f"Connecting to ADO MCP for org: {org}...")
    client = AzureDevOpsMCPClient(org)
    await client.connect()
    
    print(f"Connected! Found {len(client.get_tools())} tools")
    
    # Try creating a test Epic
    print("\nCreating test Epic...")
    result = await client.call_tool("wit_create_work_item", {
        "project": project,
        "workItemType": "Epic",
        "fields": [
            {"name": "System.Title", "value": "Test Epic from Script"},
            {"name": "System.Description", "value": "This is a test epic created by the test script"}
        ]
    })
    
    print(f"Result: {result}")
    return result

if __name__ == "__main__":
    result = asyncio.run(test_ado_tool())
    print("\n✅ Test completed!")
