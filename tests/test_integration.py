"""Integration tests for the GitHub MCP Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp.types import Tool as MCPTool


class TestGitHubMCPIntegration:
    """Integration tests for GitHub MCP connectivity."""

    @pytest.fixture
    def mock_mcp_tools(self):
        """Create mock MCP tools similar to GitHub MCP server."""
        return [
            MCPTool(
                name="list_repositories",
                description="List repositories for a user or organization",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                    },
                    "required": ["owner"],
                },
            ),
            MCPTool(
                name="get_repository",
                description="Get repository details",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            MCPTool(
                name="search_code",
                description="Search code in repositories",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_mcp_client_lists_tools(self, mock_mcp_tools):
        """Test that MCP client can list tools from the server."""
        from src.mcp_client import GitHubMCPClient

        client = GitHubMCPClient(
            mcp_url="https://api.githubcopilot.com/mcp/",
            github_token="mock-token",
        )

        # Mock the connection
        client._tools = mock_mcp_tools

        tools = await client.list_tools()
        assert len(tools) == 3
        assert tools[0].name == "list_repositories"

    @pytest.mark.asyncio
    async def test_agent_uses_mcp_tools(self, mock_mcp_tools):
        """Test that the agent correctly uses MCP tools."""
        from src.mcp_client import GitHubMCPClient, mcp_tools_to_langchain

        client = GitHubMCPClient(
            mcp_url="https://api.githubcopilot.com/mcp/",
        )
        client._tools = mock_mcp_tools

        # Mock the tool executor
        async def mock_executor(tool_name: str, args: dict):
            return {"tool": tool_name, "args": args, "result": "mocked"}

        lc_tools = mcp_tools_to_langchain(mock_mcp_tools, mock_executor)

        assert len(lc_tools) == 3
        assert lc_tools[0].name == "list_repositories"
        assert lc_tools[1].name == "get_repository"
        assert lc_tools[2].name == "search_code"

    @pytest.mark.asyncio
    async def test_orchestrator_with_github_agent(self, mock_mcp_tools):
        """Test orchestrator routing to GitHub agent."""
        from src.agents import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Found 5 repositories")

        orchestrator.register_agent("github", mock_agent, default=True)

        result = await orchestrator.route_request("List my repositories")

        assert "repositories" in result.lower()
        mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_execution(self, mock_mcp_tools):
        """Test multi-step workflow with GitHub agent."""
        from src.agents import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            side_effect=[
                "Repository: my-project",
                "Found 10 issues",
                "Created summary report",
            ]
        )

        orchestrator.register_agent("github", mock_agent)

        workflow = [
            {"name": "get_repo", "agent": "github", "message": "Get repo info"},
            {"name": "get_issues", "agent": "github", "message": "List issues for {get_repo}"},
            {"name": "summarize", "agent": "github", "message": "Summarize {get_issues}"},
        ]

        results = await orchestrator.execute_workflow(workflow)

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert results[2]["result"] == "Created summary report"


class TestMCPServerConfiguration:
    """Tests for MCP server configuration."""

    def test_mcp_config_in_workspace(self):
        """Verify the MCP configuration is correctly set up."""
        import json
        from pathlib import Path

        mcp_config_path = Path("/Users/rameshappat/Downloads/pythonmcpproject/.vscode/mcp.json")

        if mcp_config_path.exists():
            with open(mcp_config_path) as f:
                config = json.load(f)

            assert "servers" in config
            assert "github" in config["servers"]
            assert config["servers"]["github"]["url"] == "https://api.githubcopilot.com/mcp/"
