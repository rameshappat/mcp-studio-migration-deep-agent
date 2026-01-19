#!/usr/bin/env python3
"""Debug script to test GitHub MCP connection and list available tools."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    mcp_url = os.getenv("GITHUB_MCP_URL")
    token = os.getenv("GITHUB_TOKEN")
    
    print(f"MCP URL: {mcp_url}")
    print(f"Token: {token[:20]}..." if token else "Token: None")
    
    if not mcp_url or not token:
        print("ERROR: GITHUB_MCP_URL and GITHUB_TOKEN must be set")
        return
    
    from src.mcp_client.github_client import GitHubMCPClient
    
    client = GitHubMCPClient(mcp_url=mcp_url, github_token=token)
    
    print("\nConnecting to GitHub MCP...")
    await client.connect()
    
    print("\nAvailable tools:")
    tools = await client.list_tools()
    for tool in tools:
        print(f"  - {tool.name}")
        if hasattr(tool, 'description'):
            print(f"    {tool.description[:100]}...")
        if hasattr(tool, 'inputSchema'):
            params = tool.inputSchema.get('properties', {}).keys()
            print(f"    Params: {list(params)}")
        print()

if __name__ == "__main__":
    asyncio.run(main())