"""Main entry point for the MCP Agent application."""

import argparse
import asyncio
import logging
import os

from src.agents import AgentOrchestrator, create_github_agent
from src.config import config
from src.observability import setup_langsmith

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_agent() -> None:
    """Run the agent application."""
    # Validate configuration
    missing = config.validate()
    if missing:
        logger.warning(f"Missing configuration: {', '.join(missing)}")
        logger.info("Running in demo mode without API calls")
        demo_mode()
        return

    # Setup LangSmith observability
    setup_langsmith(
        api_key=config.langsmith_api_key,
        project=config.langsmith_project,
        tracing_enabled=config.langsmith_tracing,
    )

    # Create the GitHub agent
    logger.info("Creating GitHub Agent...")
    github_agent = await create_github_agent(
        mcp_url=config.github_mcp_url,
        github_token=config.github_token,
    )

    # Create orchestrator and register agent
    orchestrator = AgentOrchestrator()
    orchestrator.register_agent("github", github_agent, default=True)

    # Interactive loop
    print("\n" + "=" * 60)
    print("GitHub MCP Agent")
    print("=" * 60)
    print("Available tools:", github_agent.get_available_tools()[:5], "...")
    print("\nType your requests or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if not user_input:
                continue

            response = await orchestrator.route_request(user_input)
            print(f"\nAgent: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\nError: {e}\n")


def demo_mode() -> None:
    """Run in demo mode without API calls."""
    print("\n" + "=" * 60)
    print("GitHub MCP Agent - Demo Mode")
    print("=" * 60)
    print("\nTo use the full agent, set the following environment variables:")
    print("  - OPENAI_API_KEY: Your OpenAI API key")
    print("  - GITHUB_TOKEN: Your GitHub token (optional)")
    print("  - LANGSMITH_API_KEY: Your LangSmith API key (optional)")
    print("\nCopy .env.example to .env and fill in your values.")
    print("\nProject structure created successfully!")
    print("\nFiles created:")
    print("  - src/mcp_client/     - MCP client for GitHub")
    print("  - src/agents/         - LangGraph agent and orchestrator")
    print("  - src/observability/  - LangSmith integration")
    print("  - tests/              - Test files")
async def run_sdlc_pipeline(mode: str = "fixed", project_idea: str = None, project_name: str = None) -> None:
    """Run the SDLC pipeline in fixed or deep agent mode.
    
    Args:
        mode: 'fixed' for fixed graph, 'deep' for deep agents
        project_idea: Description of the project to build
        project_name: Name of the project
    """
    if not project_idea:
        project_idea = input("Enter project idea: ").strip()
    if not project_name:
        project_name = input("Enter project name: ").strip()
    
    print(f"\n🚀 Starting SDLC Pipeline in {mode.upper()} mode")
    print(f"Project: {project_name}")
    print(f"Idea: {project_idea}\n")
    
    if mode == "deep":
        # Use new dynamic deep agent graph
        from src.studio_graph_deep import dynamic_graph
        
        # Configuration
        require_approval = os.getenv("REQUIRE_APPROVAL", "false").lower() == "true"
        confidence_threshold = os.getenv("CONFIDENCE_THRESHOLD", "medium")
        
        print(f"Configuration:")
        print(f"  - Approval: {'Required' if require_approval else 'Autonomous'}")
        print(f"  - Confidence threshold: {confidence_threshold}")
        print(f"  - Self-correction: Enabled")
        print(f"  - Agent spawning: Enabled")
        print()
        
        initial_state = {
            "project_idea": project_idea,
            "project_name": project_name,
            "require_approval": require_approval,
            "confidence_threshold": confidence_threshold,
            "max_pipeline_iterations": 20,
        }
        
        config_dict = {
            "configurable": {
                "thread_id": f"sdlc-{project_name}",
            }
        }
        
        try:
            result = await dynamic_graph.ainvoke(initial_state, config_dict)
            
            print("\n" + "="*60)
            print("Pipeline Completed!")
            print("="*60)
            print(f"Status: {'✅ Success' if result.get('completed') else '⚠️ Incomplete'}")
            print(f"Iterations: {result.get('pipeline_iteration', 0)}")
            print(f"Agents executed: {len(result.get('agent_history', []))}")
            
            artifacts = result.get('artifacts', {})
            print(f"\nArtifacts generated: {len(artifacts)}")
            for artifact_type in artifacts.keys():
                print(f"  - {artifact_type}")
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Pipeline interrupted by user")
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
    
    else:
        # Use original fixed graph
        from src.studio_graph_agentic import graph
        
        print(f"Configuration:")
        print(f"  - Approval: Required at each stage")
        print(f"  - Flow: Fixed sequence")
        print()
        
        initial_state = {
            "project_idea": project_idea,
            "project_name": project_name,
        }
        
        config_dict = {
            "configurable": {
                "thread_id": f"sdlc-fixed-{project_name}",
            }
        }
        
        try:
            result = await graph.ainvoke(initial_state, config_dict)
            
            print("\n" + "="*60)
            print("Pipeline Completed!")
            print("="*60)
            print(f"Final stage: {result.get('current_stage', 'unknown')}")
            
            if result.get('requirements'):
                print("✓ Requirements generated")
            if result.get('epics'):
                print(f"✓ Epics created: {len(result.get('epics', []))}")
            if result.get('architecture'):
                print("✓ Architecture designed")
            if result.get('code_artifacts'):
                print("✓ Code generated")
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Pipeline interrupted by user")
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Agent Application")
    parser.add_argument(
        "--mode",
        choices=["agent", "sdlc-fixed", "sdlc-deep"],
        default="agent",
        help="Mode to run: agent (interactive), sdlc-fixed (fixed pipeline), sdlc-deep (deep agents)",
    )
    parser.add_argument(
        "--project-idea",
        type=str,
        help="Project idea for SDLC pipeline",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        help="Project name for SDLC pipeline",
    )
    
    args = parser.parse_args()
    
    if args.mode == "agent":
        asyncio.run(run_agent())
    elif args.mode == "sdlc-fixed":
        asyncio.run(run_sdlc_pipeline("fixed", args.project_idea, args.project_name))
    elif args.mode == "sdlc-deep":
        asyncio.run(run_sdlc_pipeline("deep", args.project_idea, args.project_name
    """Main entry point."""
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
