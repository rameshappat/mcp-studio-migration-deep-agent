"""GitHub Agent using LangGraph for orchestration."""

import logging
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.mcp_client import GitHubMCPClient, mcp_tools_to_langchain

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the GitHub agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    tool_calls_count: int
    max_tool_calls: int


class GitHubAgent:
    """Agent for interacting with GitHub via MCP."""

    def __init__(
        self,
        mcp_client: GitHubMCPClient,
        model_name: str = "gpt-4o-mini",
        max_tool_calls: int = 10,
    ):
        """Initialize the GitHub Agent.

        Args:
            mcp_client: The MCP client for GitHub.
            model_name: The OpenAI model to use.
            max_tool_calls: Maximum number of tool calls per request.
        """
        self.mcp_client = mcp_client
        self.model_name = model_name
        self.max_tool_calls = max_tool_calls
        self._graph = None
        self._tools = []

    async def initialize(self) -> None:
        """Initialize the agent with tools from MCP."""
        logger.info("Initializing GitHub Agent...")

        # Get tools from MCP server
        mcp_tools = await self.mcp_client.list_tools()
        logger.info(f"Loaded {len(mcp_tools)} tools from MCP server")

        # Convert to LangChain tools
        self._tools = mcp_tools_to_langchain(
            mcp_tools,
            self.mcp_client.call_tool,
        )

        # Build the graph
        self._graph = self._build_graph()
        logger.info("GitHub Agent initialized successfully")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Initialize the LLM with tools
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        llm_with_tools = llm.bind_tools(self._tools)

        # Define the agent node
        def agent_node(state: AgentState) -> dict[str, Any]:
            """Process messages and decide on tool calls."""
            messages = state["messages"]
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

        # Define the tool node
        tool_node = ToolNode(self._tools)

        # Define the routing function
        def should_continue(state: AgentState) -> str:
            """Determine if we should continue or end."""
            messages = state["messages"]
            last_message = messages[-1]

            # Check tool call limit
            if state.get("tool_calls_count", 0) >= state.get("max_tool_calls", 10):
                logger.warning("Max tool calls reached")
                return END

            # If the last message has tool calls, route to tools
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"

            return END

        # Increment tool call counter
        def increment_counter(state: AgentState) -> dict[str, int]:
            """Increment the tool calls counter."""
            return {"tool_calls_count": state.get("tool_calls_count", 0) + 1}

        # Build the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("counter", increment_counter)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add edges
        workflow.add_conditional_edges("agent", should_continue, {"tools": "counter", END: END})
        workflow.add_edge("counter", "tools")
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def run(self, user_message: str) -> str:
        """Run the agent with a user message.

        Args:
            user_message: The user's input message.

        Returns:
            The agent's response.
        """
        if not self._graph:
            await self.initialize()

        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_message)],
            "tool_calls_count": 0,
            "max_tool_calls": self.max_tool_calls,
        }

        # Run the graph
        result = await self._graph.ainvoke(initial_state)

        # Extract the final response
        messages = result["messages"]
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return str(msg.content)

        return "No response generated"

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        return [tool.name for tool in self._tools]


async def create_github_agent(
    mcp_url: str,
    github_token: str | None = None,
    model_name: str = "gpt-4o-mini",
) -> GitHubAgent:
    """Factory function to create and initialize a GitHub agent.

    Args:
        mcp_url: URL of the GitHub MCP server.
        github_token: Optional GitHub token.
        model_name: OpenAI model to use.

    Returns:
        Initialized GitHubAgent instance.
    """
    client = GitHubMCPClient(mcp_url, github_token)
    agent = GitHubAgent(client, model_name)
    await agent.initialize()
    return agent
