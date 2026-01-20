#!/usr/bin/env python3
"""Test script to verify Deep Agent tool call tracking fix."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agents.deep_agent import DeepAgent
from src.mcp_client.ado_client import AzureDevOpsMCPClient


async def test_work_items_creation():
    """Test that work items agent properly tracks tool calls."""
    
    print("=" * 80)
    print("🧪 Testing Deep Agent Tool Call Tracking Fix")
    print("=" * 80)
    
    # Initialize MCP client (ADO only)
    print("\n📡 Connecting to ADO MCP client...")
    ado_client = AzureDevOpsMCPClient()
    
    try:
        await ado_client.connect()
        tools = ado_client.get_langchain_tools()
        print(f"✅ Connected! Loaded {len(tools)} ADO tools")
        
        # Create Deep Agent with ADO tools
        print("\n🤖 Creating Business Analyst Deep Agent...")
        agent = DeepAgent(
            role="Business Analyst",
            goal="Create work items in Azure DevOps",
            backstory="Expert at breaking down requirements into actionable work items",
            tools=tools,
            max_iterations=3,
        )
        print("✅ Agent created")
        
        # Simple task to create ONE work item
        task = """
Create ONE work item in Azure DevOps for project "testingmcp":

Title: "Test Deep Agent Fix - API Authentication"
Description: "Implement OAuth 2.0 authentication for user login endpoints"
Type: "Issue"
Area Path: "testingmcp"

Use the ado_wit_create_work_item tool to create this work item.
"""
        
        print("\n🎯 Executing task...")
        print(f"Task: {task.strip()[:100]}...")
        
        result = await agent.execute(task)
        
        print("\n" + "=" * 80)
        print("📊 RESULTS")
        print("=" * 80)
        
        print(f"\n✅ Status: {result.get('status')}")
        print(f"🔄 Iterations: {result.get('iterations')}")
        print(f"🛠️  Tool calls made: {result.get('tool_calls_made', 0)}")
        
        tool_calls = result.get('tool_calls', [])
        print(f"\n📋 Tool calls list length: {len(tool_calls)}")
        
        if tool_calls:
            print("\n🔍 Tool call details:")
            for i, tc in enumerate(tool_calls, 1):
                print(f"\n  {i}. Tool: {tc.get('tool')}")
                print(f"     Args: {tc.get('args', {})}")
                result_text = tc.get('result', {}).get('text', '')
                print(f"     Result preview: {result_text[:200]}...")
        else:
            print("\n❌ NO TOOL CALLS RECORDED!")
            print("   This is the bug we're trying to fix.")
        
        # Check output
        output = result.get('output', '')
        print(f"\n📝 Output length: {len(output)} characters")
        print(f"📝 Output preview:\n{output[:300]}...")
        
        # Verdict
        print("\n" + "=" * 80)
        if tool_calls and any('wit_create_work_item' in tc.get('tool', '') for tc in tool_calls):
            print("✅ SUCCESS: Tool calls are being tracked properly!")
            print("   The fix is working - tool_calls list is populated")
        elif result.get('tool_calls_made', 0) > 0 and not tool_calls:
            print("⚠️  PARTIAL: tool_calls_made > 0 but tool_calls list is empty")
            print("   This suggests the old code path")
        else:
            print("❌ FAILURE: No tool calls made")
            print("   This could mean:")
            print("   1. LLM didn't generate tool calls (too many tools?)")
            print("   2. Tool execution failed")
            print("   3. Agent decided not to use tools")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔌 Disconnecting...")
        await ado_client.disconnect()
        print("✅ Disconnected")


if __name__ == "__main__":
    asyncio.run(test_work_items_creation())
