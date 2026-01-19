#!/usr/bin/env python
"""Test MCP Client Connections with Environment Tokens."""

import asyncio
import sys
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("MCP CLIENT CONNECTION TEST")
print("=" * 60)

# Test 1: ADO MCP Client
print("\n1. Testing Azure DevOps MCP Client...")
try:
    from src.mcp_client.ado_client import AzureDevOpsMCPClient
    
    org = os.getenv('AZURE_DEVOPS_ORGANIZATION')
    proj = os.getenv('AZURE_DEVOPS_PROJECT')
    
    if not org:
        print(f"   ⚠️  ADO MCP: AZURE_DEVOPS_ORGANIZATION not set")
    else:
        async def test_ado():
            client = AzureDevOpsMCPClient(
                organization=org,
                project=proj,
                auth_type='envvar'
            )
            await client.connect()
            tools = client.get_tools()
            print(f"   ✅ ADO MCP Connected")
            print(f"   ✅ Organization: {org}")
            print(f"   ✅ Project: {proj}")
            print(f"   ✅ Tools Available: {len(tools)}")
            
            # Show sample tool names
            if tools:
                tool_names = [t.get('name', 'unknown') for t in tools[:5]]
                print(f"   ✅ Sample Tools: {', '.join(tool_names)}")
            
            await client.close()
            return True
        
        asyncio.run(test_ado())
    
except Exception as e:
    print(f"   ❌ ADO MCP Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: GitHub MCP Client
print("\n2. Testing GitHub MCP Client...")
try:
    from src.mcp_client.github_client import GitHubMCPClient
    
    mcp_url = os.getenv('GITHUB_MCP_URL')
    token = os.getenv('GITHUB_TOKEN')
    
    if not mcp_url:
        print(f"   ⚠️  GitHub MCP: GITHUB_MCP_URL not set")
    elif not token:
        print(f"   ⚠️  GitHub MCP: GITHUB_TOKEN not set")
    else:
        async def test_github():
            client = GitHubMCPClient(
                mcp_url=mcp_url,
                github_token=token
            )
            await client.connect()
            tools = client.get_tools()
            print(f"   ✅ GitHub MCP Connected")
            print(f"   ✅ Owner: {os.getenv('GITHUB_OWNER')}")
            print(f"   ✅ Tools Available: {len(tools)}")
            
            # Show sample tool names
            if tools:
                tool_names = [t.get('name', 'unknown') for t in tools[:5]]
                print(f"   ✅ Sample Tools: {', '.join(tool_names)}")
            
            await client.close()
            return True
        
        asyncio.run(test_github())
    
except Exception as e:
    print(f"   ⚠️  GitHub MCP Warning: {e}")
    import traceback
    traceback.print_exc()
    print(f"   Note: GitHub MCP may require additional configuration")

# Test 3: Mermaid MCP Client
print("\n3. Testing Mermaid MCP Client...")
try:
    from src.mcp_client.mermaid_client import MermaidMCPClient
    
    async def test_mermaid():
        client = MermaidMCPClient()
        await client.connect()
        tools = client.get_tools()
        print(f"   ✅ Mermaid MCP Connected")
        print(f"   ✅ Tools Available: {len(tools)}")
        
        # Show tool names
        if tools:
            tool_names = [t.get('name', 'unknown') for t in tools]
            print(f"   ✅ Tools: {', '.join(tool_names)}")
        
        # No disconnect method needed for Mermaid
        return True
    
    asyncio.run(test_mermaid())
    
except Exception as e:
    print(f"   ⚠️  Mermaid MCP Warning: {e}")
    print(f"   Note: Mermaid MCP is optional for diagram generation")

# Final Summary
print("\n" + "=" * 60)
print("✅ MCP CONNECTION TEST COMPLETE")
print("=" * 60)
print("\nEnvironment Configuration:")
print(f"  • OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else 'Missing'}")
print(f"  • ANTHROPIC_API_KEY: {'Set' if os.getenv('ANTHROPIC_API_KEY') else 'Missing'}")
print(f"  • LANGSMITH_API_KEY: {'Set' if os.getenv('LANGSMITH_API_KEY') else 'Missing'}")
print(f"  • GITHUB_TOKEN: {'Set' if os.getenv('GITHUB_TOKEN') else 'Missing'}")
print(f"  • ADO_MCP_AUTH_TOKEN: {'Set' if os.getenv('ADO_MCP_AUTH_TOKEN') else 'Missing'}")
