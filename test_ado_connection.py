#!/usr/bin/env python3
"""Test script to verify Azure DevOps MCP connection and tools."""

import asyncio
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_ado_mcp():
    """Test connection to Azure DevOps MCP server."""
    
    org = os.environ.get("AZURE_DEVOPS_ORGANIZATION", "appatr")
    project = os.environ.get("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    # Check for PAT - the MCP server expects ADO_MCP_AUTH_TOKEN for envvar auth
    pat = os.environ.get("ADO_MCP_AUTH_TOKEN") or os.environ.get("AZURE_DEVOPS_EXT_PAT") or os.environ.get("AZURE_DEVOPS_PAT", "")
    if pat:
        print(f"🔑 Using PAT authentication (token ends with: ...{pat[-8:]})")
        auth_type = "envvar"  # Correct auth type for PAT
    else:
        print("📝 Using interactive authentication - browser may open for login")
        auth_type = "interactive"
    
    print(f"🔧 Connecting to Azure DevOps MCP for org: {org}, project: {project}")
    
    # Build environment with PAT explicitly passed to child process
    env = {**os.environ}
    if pat:
        env["ADO_MCP_AUTH_TOKEN"] = pat
    
    # Use envvar auth if PAT is available, otherwise interactive
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@azure-devops/mcp", org, "-a", auth_type, "-d", "core", "work", "work-items"],
        env=env,
    )
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # List tools
            tools_result = await session.list_tools()
            print(f"\n✅ Connected! Found {len(tools_result.tools)} tools:\n")
            
            # Show work item related tools
            wit_tools = [t for t in tools_result.tools if "work" in t.name.lower() or "wit" in t.name.lower()]
            print("📋 Work Item Tools:")
            for tool in wit_tools:
                print(f"  - {tool.name}")
                if tool.inputSchema and "properties" in tool.inputSchema:
                    props = tool.inputSchema["properties"]
                    required = tool.inputSchema.get("required", [])
                    print(f"    Required params: {required}")
                    print(f"    All params: {list(props.keys())}")
                print()
            
            # Try to create a test work item
            print("\n🧪 Testing work item creation...")
            create_tool = "wit_create_work_item"
            
            # Find the tool to check its exact parameters
            for tool in tools_result.tools:
                if tool.name == create_tool:
                    print(f"\n📝 {create_tool} schema:")
                    print(json.dumps(tool.inputSchema, indent=2))
                    break
            
            # Try creating a test Epic
            try:
                result = await session.call_tool(
                    create_tool,
                    {
                        "project": project,
                        "workItemType": "Epic",
                        "fields": [
                            {"name": "System.Title", "value": "Test Epic - Created via MCP"},
                            {"name": "System.Description", "value": "This is a test epic created via the Azure DevOps MCP server."},
                        ],
                    },
                )
                print(f"\n✅ Created test Epic!")
                if result.content:
                    content = result.content[0]
                    if hasattr(content, 'text'):
                        print(f"Result: {content.text[:500]}")
            except Exception as e:
                print(f"\n❌ Failed to create Epic: {e}")

if __name__ == "__main__":
    asyncio.run(test_ado_mcp())
