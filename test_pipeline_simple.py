#!/usr/bin/env python3
"""Simple pipeline test - no user input required."""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.studio_graph_autonomous import build_graph

async def main():
    print("\n" + "=" * 80)
    print("TESTING SDLC PIPELINE")
    print("=" * 80)
    
    graph = build_graph()
    
    state = {
        "user_query": "Build a simple todo list API with CRUD operations",
        "project_name": "todo-api-test"
    }
    
    print(f"\n📝 Project: {state['project_name']}")
    print(f"📋 Query: {state['user_query']}")
    print("\n" + "-" * 80)
    
    config = {"configurable": {"thread_id": "test-simple-001"}}
    
    try:
        async for event in graph.astream(state, config):
            for node_name, output in event.items():
                # Skip internal nodes
                if node_name.startswith("_"):
                    continue
                    
                print(f"\n{'='*80}")
                print(f"NODE: {node_name}")
                print(f"{'='*80}")
                
                # Show key outputs
                if "messages" in output and output["messages"]:
                    msg = output["messages"][0] if isinstance(output["messages"], list) else output["messages"]
                    if isinstance(msg, dict):
                        print(f"  ✓ {msg.get('content', '')}")
                
                if "test_cases" in output and output["test_cases"]:
                    print(f"  ✓ Test cases created: {len(output['test_cases'])}")
                
                if "github_results" in output and output["github_results"]:
                    result = output["github_results"]
                    if isinstance(result, dict):
                        if "error" in result:
                            print(f"  ❌ GitHub error: {result['error']}")
                        else:
                            print(f"  ✓ GitHub: {result}")
                
                if "consecutive_failures" in output:
                    failures = output["consecutive_failures"]
                    if failures:
                        print(f"  ⚠️  Failures: {failures}")
        
        print("\n" + "=" * 80)
        print("✅ PIPELINE COMPLETED")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
