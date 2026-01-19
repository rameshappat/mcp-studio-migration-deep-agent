#!/usr/bin/env python3
"""Check tool names from MCP clients."""
import asyncio
from src.mcp_client.ado_client import AzureDevOpsMCPClient
from src.mcp_client.github_client import GitHubMCPClient

async def main():
    # Check ADO client
    print("Connecting to ADO MCP...")
    ado_client = AzureDevOpsMCPClient("appatr")
    await ado_client.connect()
    ado_tools = ado_client.get_tools()
    
    print(f"\nADO tools type: {type(ado_tools)}")
    if isinstance(ado_tools, dict):
        tool_names = list(ado_tools.keys())
    elif isinstance(ado_tools, list):
        # Check if it's a list of dicts with 'name' key or objects
        if ado_tools and hasattr(ado_tools[0], 'name'):
            tool_names = [t.name for t in ado_tools]
        elif ado_tools and isinstance(ado_tools[0], dict):
            tool_names = [t.get('name', str(t)) for t in ado_tools]
        else:
            tool_names = [str(t) for t in ado_tools]
    else:
        tool_names = []
    
    print("\n=== ADO Tool Names with 'create' ===")
    for name in tool_names:
        if "create" in name.lower():
            print(f"  - {name}")
    
    # Check GitHub client  
    print("\nConnecting to GitHub MCP...")
    gh_client = GitHubMCPClient(mcp_url="http://localhost:8000")
    await gh_client.connect()
    gh_tools = gh_client.get_tools()
    
    print(f"\nGitHub tools type: {type(gh_tools)}")
    if isinstance(gh_tools, dict):
        gh_names = list(gh_tools.keys())
    elif isinstance(gh_tools, list):
        if gh_tools and hasattr(gh_tools[0], 'name'):
            gh_names = [t.name for t in gh_tools]
        elif gh_tools and isinstance(gh_tools[0], dict):
            gh_names = [t.get('name', str(t)) for t in gh_tools]
        else:
            gh_names = [str(t) for t in gh_tools]
    else:
        gh_names = []
    
    print("\n=== GitHub Tool Names with 'create' or 'update' ===")
    for name in gh_names:
        if "create" in name.lower() or "update" in name.lower():
            print(f"  - {name}")

if __name__ == "__main__":
    asyncio.run(main())
