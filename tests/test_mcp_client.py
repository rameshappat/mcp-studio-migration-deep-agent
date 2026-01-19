"""Tests for the MCP client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.mcp_client.github_client import GitHubMCPClient
from src.mcp_client.tool_converter import mcp_tools_to_langchain, format_tool_for_display
from mcp.types import Tool as MCPTool


class TestGitHubMCPClient:
    """Tests for GitHubMCPClient."""

    def test_init(self):
        """Test client initialization."""
        client = GitHubMCPClient(
            mcp_url="https://api.example.com/mcp/",
            github_token="test-token",
        )
        assert client.mcp_url == "https://api.example.com/mcp"
        assert client.github_token == "test-token"
        assert client._tools == []

    def test_get_headers_with_token(self):
        """Test headers include authorization when token is set."""
        client = GitHubMCPClient(
            mcp_url="https://api.example.com/mcp/",
            github_token="test-token",
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_without_token(self):
        """Test headers without authorization when no token."""
        client = GitHubMCPClient(
            mcp_url="https://api.example.com/mcp/",
        )
        headers = client._get_headers()
        assert "Authorization" not in headers

    def test_get_tool_names_empty(self):
        """Test getting tool names when no tools loaded."""
        client = GitHubMCPClient(mcp_url="https://api.example.com/mcp/")
        assert client.get_tool_names() == []

    def test_get_tool_by_name_not_found(self):
        """Test getting a tool that doesn't exist."""
        client = GitHubMCPClient(mcp_url="https://api.example.com/mcp/")
        assert client.get_tool_by_name("nonexistent") is None


class TestToolConverter:
    """Tests for MCP to LangChain tool conversion."""

    def test_format_tool_for_display(self):
        """Test formatting a tool for display."""
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "number"},
                },
                "required": ["param1"],
            },
        )
        result = format_tool_for_display(tool)
        assert "test_tool" in result
        assert "A test tool" in result
        assert "param1" in result
        assert "required" in result

    def test_format_tool_no_params(self):
        """Test formatting a tool with no parameters."""
        tool = MCPTool(
            name="simple_tool",
            description="Simple tool",
            inputSchema={},
        )
        result = format_tool_for_display(tool)
        assert "simple_tool" in result
        assert "No parameters" in result

    @pytest.mark.asyncio
    async def test_mcp_tools_to_langchain(self):
        """Test converting MCP tools to LangChain tools."""
        mcp_tools = [
            MCPTool(
                name="list_repos",
                description="List repositories",
                inputSchema={
                    "type": "object",
                    "properties": {"owner": {"type": "string"}},
                },
            ),
        ]

        async def mock_executor(tool_name: str, args: dict):
            return {"result": "success"}

        lc_tools = mcp_tools_to_langchain(mcp_tools, mock_executor)
        assert len(lc_tools) == 1
        assert lc_tools[0].name == "list_repos"
