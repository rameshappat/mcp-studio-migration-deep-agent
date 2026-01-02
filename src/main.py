"""Main entry point for the MCP Agent application."""

import asyncio
import logging

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


def main() -> None:
    """Main entry point."""
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
