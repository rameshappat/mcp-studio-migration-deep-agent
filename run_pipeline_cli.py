#!/usr/bin/env python3
"""
Run the SDLC pipeline from command line for testing and debugging.
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.studio_graph_autonomous import build_graph


async def main():
    """Run the pipeline with a sample user query."""
    
    print("=" * 80)
    print("SDLC PIPELINE - COMMAND LINE EXECUTION")
    print("=" * 80)
    
    # Build the graph
    print("\n🔨 Building graph...")
    compiled = build_graph()
    
    # Initial state
    user_query = input("\n📝 Enter your project description (or press Enter for default): ").strip()
    if not user_query:
        user_query = "Build a financial user registration API with multi-factor authentication"
    
    project_name = input("📁 Enter project name (or press Enter for default): ").strip()
    if not project_name:
        project_name = "fin-usr-reg-with-mfa"
    
    initial_state = {
        "user_query": user_query,
        "project_name": project_name,
    }
    
    print(f"\n🚀 Starting pipeline...")
    print(f"   Query: {user_query}")
    print(f"   Project: {project_name}")
    print("-" * 80)
    
    config = {"configurable": {"thread_id": "cli-test-run"}}
    
    # Run the graph and stream results
    try:
        interrupted = False
        async for event in compiled.astream(initial_state, config):
            for node_name, node_output in event.items():
                print(f"\n{'=' * 80}")
                print(f"NODE: {node_name}")
                print(f"{'=' * 80}")
                
                # Check if we hit an interrupt
                if node_name == "__interrupt__":
                    print("⏸️  Pipeline interrupted for approval")
                    interrupted = True
                    break
                
                # Print relevant outputs
                if "messages" in node_output and node_output["messages"]:
                    for msg in node_output["messages"]:
                        if isinstance(msg, dict):
                            print(f"  📨 {msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}")
                        else:
                            print(f"  📨 {msg}")
                
                if "current_agent" in node_output:
                    print(f"  🎯 Next: {node_output['current_agent']}")
                
                if "requires_approval" in node_output and node_output["requires_approval"]:
                    print(f"  ⏸️  REQUIRES APPROVAL")
                
                if "test_cases" in node_output and node_output["test_cases"]:
                    print(f"  🧪 Test cases created: {len(node_output['test_cases'])}")
                
                if "github_results" in node_output and node_output["github_results"]:
                    print(f"  🐙 GitHub results: {node_output['github_results']}")
                
                print(f"{'=' * 80}")
        
        # If interrupted, auto-approve and continue
        if interrupted:
            print("\n⏭️  Auto-approving to continue pipeline...")
            # Update with approval and resume
            async for event in compiled.astream({"approval_response": "approved"}, config):
                for node_name, node_output in event.items():
                    print(f"\n{'=' * 80}")
                    print(f"NODE: {node_name}")
                    print(f"{'=' * 80}")
                    
                    # Print relevant outputs (same as above)
                    if "messages" in node_output and node_output["messages"]:
                        for msg in node_output["messages"]:
                            if isinstance(msg, dict):
                                print(f"  📨 {msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}")
                    
                    if "current_agent" in node_output:
                        print(f"  🎯 Next: {node_output['current_agent']}")
                    
                    if "test_cases" in node_output and node_output["test_cases"]:
                        print(f"  🧪 Test cases created: {len(node_output['test_cases'])}")
                    
                    if "github_results" in node_output and node_output["github_results"]:
                        print(f"  🐙 GitHub results: {node_output['github_results']}")
                    
                    print(f"{'=' * 80}")
        
        print("\n✅ Pipeline completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
