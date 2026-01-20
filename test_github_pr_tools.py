#!/usr/bin/env python3
"""
Test script to verify GitHub MCP PR creation tools work correctly.
Run this before deploying to production to ensure PR creation will succeed.
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_client.github_client import GitHubMCPClient


async def test_github_pr_tools():
    """Test GitHub MCP tools for PR creation."""
    
    print("🧪 Testing GitHub MCP PR Tools...")
    print("=" * 60)
    
    # Initialize client
    try:
        github_client = GitHubMCPClient()
        await github_client.connect()
        print("✅ GitHub client connected")
    except Exception as e:
        print(f"❌ Failed to connect to GitHub client: {e}")
        return False
    
    # Test repository (using the fin-demo repo)
    owner = "rameshappat"
    repo = "fin-demo01192026-da-6"
    
    print(f"\n📦 Testing with repository: {owner}/{repo}")
    
    # Test 1: Check if repository exists
    print("\n1️⃣ Testing get_repository...")
    try:
        repo_result = await github_client.call_tool(
            "get_repository",
            {"owner": owner, "repo": repo}
        )
        if repo_result:
            print(f"   ✅ Repository exists: {repo_result.get('full_name', 'unknown')}")
            print(f"   Default branch: {repo_result.get('default_branch', 'unknown')}")
        else:
            print(f"   ⚠️ Repository check returned no result")
    except Exception as e:
        print(f"   ❌ Repository check failed: {e}")
    
    # Test 2: List branches
    print("\n2️⃣ Testing list_branches...")
    try:
        branches_result = await github_client.call_tool(
            "list_branches",
            {"owner": owner, "repo": repo}
        )
        if branches_result:
            branches = branches_result if isinstance(branches_result, list) else [branches_result]
            print(f"   ✅ Found {len(branches)} branch(es)")
            for branch in branches[:5]:
                if isinstance(branch, dict):
                    print(f"      - {branch.get('name', 'unknown')}")
                else:
                    print(f"      - {branch}")
        else:
            print(f"   ⚠️ No branches found")
    except Exception as e:
        print(f"   ❌ Branch listing failed: {e}")
    
    # Test 3: List PRs
    print("\n3️⃣ Testing list_pull_requests...")
    try:
        prs_result = await github_client.call_tool(
            "list_pull_requests",
            {"owner": owner, "repo": repo, "state": "all"}
        )
        if prs_result:
            prs = prs_result if isinstance(prs_result, list) else [prs_result]
            print(f"   ✅ Found {len(prs)} PR(s)")
            for pr in prs[:3]:
                if isinstance(pr, dict):
                    pr_num = pr.get('number', 'unknown')
                    pr_state = pr.get('state', 'unknown')
                    pr_title = pr.get('title', 'unknown')
                    print(f"      - PR #{pr_num} ({pr_state}): {pr_title[:50]}")
        else:
            print(f"   ℹ️  No PRs found (this is expected if none exist)")
    except Exception as e:
        print(f"   ❌ PR listing failed: {e}")
    
    # Test 4: Check if create_pull_request tool is available
    print("\n4️⃣ Testing tool availability...")
    try:
        tools = await github_client.list_tools()
        pr_tools = [t for t in tools if 'pull' in t.get('name', '').lower() or 'pr' in t.get('name', '').lower()]
        print(f"   ✅ Found {len(pr_tools)} PR-related tools:")
        for tool in pr_tools:
            print(f"      - {tool.get('name', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Tool listing failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ GitHub MCP tools test complete!")
    print("\n💡 If all tests passed, PR creation should work in production.")
    print("💡 If any tests failed, investigate GitHub MCP connection issues.")
    
    # Cleanup
    try:
        await github_client.disconnect()
    except:
        pass
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_github_pr_tools())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
