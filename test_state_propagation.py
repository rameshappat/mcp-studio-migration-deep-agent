"""Quick test to verify state propagation between nodes."""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.studio_graph_autonomous import build_graph

async def test_state():
    graph = build_graph()
    
    # Run a minimal test
    initial_state = {
        "user_query": "Create a simple user registration feature",
        "project_name": "test-propagation"
    }
    
    print("🚀 Starting state propagation test...")
    print("=" * 60)
    
    async for event in graph.astream(initial_state):
        for node_name, node_output in event.items():
            if node_name == "work_items":
                print(f"\n📦 WORK_ITEMS NODE OUTPUT:")
                print(f"  - Keys: {list(node_output.keys())}")
                print(f"  - work_items field: {node_output.get('work_items')}")
                if 'work_items' in node_output:
                    wi = node_output['work_items']
                    if isinstance(wi, dict):
                        print(f"  - created_ids: {wi.get('created_ids', 'NOT FOUND')}")
            
            elif node_name == "test_plan":
                print(f"\n📋 TEST_PLAN NODE RECEIVED:")
                # This is what the node received as INPUT (the full state)
                # We need to check what it sees
                pass
            
            elif node_name == "orchestrator":
                if "work_items" in node_output:
                    print(f"\n🎯 ORCHESTRATOR AFTER work_items:")
                    print(f"  - work_items in output: {node_output.get('work_items')}")

if __name__ == "__main__":
    asyncio.run(test_state())
