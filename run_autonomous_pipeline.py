#!/usr/bin/env python3
"""Run the autonomous SDLC pipeline from command line.

This script executes the optimized autonomous pipeline with Deep Agents.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.studio_graph_autonomous import graph


async def run_autonomous_pipeline(user_query: str, project_name: str):
    """Run the autonomous SDLC pipeline."""
    
    print("\n" + "=" * 70)
    print("🚀 Autonomous SDLC Pipeline with Deep Agents")
    print("=" * 70)
    print(f"\n📋 Project: {project_name}")
    print(f"📝 Query: {user_query}")
    print("\n" + "=" * 70 + "\n")
    
    # Initial state
    initial_state = {
        "user_query": user_query,
        "project_name": project_name,
        "messages": [],
    }
    
    # Stream through the graph
    print("🔄 Starting pipeline...\n")
    
    try:
        async for event in graph.astream(
            initial_state,
            config={"recursion_limit": 50}  # Increased limit
        ):
            # Print node execution
            for node_name, node_output in event.items():
                if node_name == "orchestrator":
                    current_agent = node_output.get("current_agent", "unknown")
                    print(f"🎯 Orchestrator → {current_agent}")
                elif node_name in ["requirements", "work_items", "test_plan", "architecture", "development"]:
                    print(f"✅ {node_name.title()} step complete")
                    
                    # Print any messages
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, dict):
                            content = msg.get("content", "")
                            if content:
                                print(f"   {content}")
        
        print("\n" + "=" * 70)
        print("✅ Pipeline completed successfully!")
        print("=" * 70 + "\n")
        
        # Get final state
        final_state = await graph.ainvoke(initial_state, config={"recursion_limit": 50})
        
        # Print summary
        print("📊 Pipeline Summary:")
        print(f"  • Requirements: {'✅' if final_state.get('requirements') else '❌'}")
        print(f"  • Work Items: {'✅' if final_state.get('work_items') else '❌'}")
        print(f"  • Test Cases: {'✅' if final_state.get('test_cases') else '❌'}")
        print(f"  • Architecture: {'✅' if final_state.get('architecture') else '❌'}")
        print(f"  • Code: {'✅' if final_state.get('code_artifacts') else '❌'}")
        print(f"  • GitHub PR: {'✅' if final_state.get('github_results') else '❌'}")
        print()
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run autonomous SDLC pipeline")
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default="Create a REST API for task management with user authentication",
        help="User query describing the project"
    )
    parser.add_argument(
        "--project",
        "-p",
        type=str,
        default="task-api",
        help="Project name"
    )
    
    args = parser.parse_args()
    
    await run_autonomous_pipeline(args.query, args.project)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Pipeline interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
