"""GitHub MCP Client for connecting to the GitHub MCP Server via stdio."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class GitHubMCPClient:
    """Client for interacting with the GitHub MCP Server via stdio.
    
    Uses the @modelcontextprotocol/server-github npm package.
    """

    def __init__(self, github_token: str | None = None):
        """Initialize the GitHub MCP Client.

        Args:
            github_token: GitHub Personal Access Token for authentication.
                         Falls back to GITHUB_TOKEN env var if not provided.
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self._tools: list[dict] = []
        self._connected = False

    def _get_server_params(self) -> StdioServerParameters:
        """Get stdio server parameters for the GitHub MCP server."""
        return StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={
                **os.environ,
                "GITHUB_PERSONAL_ACCESS_TOKEN": self.github_token,
            },
        )

    @asynccontextmanager
    async def _get_session(self):
        """Get an MCP session as an async context manager."""
        server_params = self._get_server_params()
        
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def connect(self) -> None:
        """Test connection to the GitHub MCP server and list tools."""
        logger.info("Connecting to GitHub MCP server (stdio)")

        try:
            async with self._get_session() as session:
                # List available tools
                tools_result = await session.list_tools()
                self._tools = [
                    {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
                    for tool in tools_result.tools
                ]
                self._connected = True
                
                logger.info(f"Connected! Found {len(self._tools)} GitHub tools")
                print(f"✅ Connected to GitHub MCP. Found {len(self._tools)} tools.")
        except Exception as e:
            logger.error(f"Failed to connect to GitHub MCP: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close the connection (no-op for session-per-call model)."""
        self._connected = False
        logger.info("GitHub MCP connection closed")

    def get_tools(self) -> list[dict]:
        """Get list of available tools."""
        return self._tools

    def get_tool_names(self) -> list[str]:
        """Get list of tool names."""
        return [tool["name"] for tool in self._tools]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the GitHub MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The result from the tool execution.
        """
        logger.info(f"Calling GitHub tool: {tool_name}")

        async with self._get_session() as session:
            result = await session.call_tool(tool_name, arguments)
            
            # Parse the result content
            if result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"text": content.text}
            
            return result

    async def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = False,
    ) -> dict[str, Any]:
        """Create a new GitHub repository.

        Args:
            name: Repository name.
            description: Repository description.
            private: Whether the repository should be private.

        Returns:
            Created repository details.
        """
        return await self.call_tool(
            "create_repository",
            {
                "name": name,
                "description": description,
                "private": private,
            },
        )

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: File path.
            content: File content.
            message: Commit message.
            branch: Branch name.
            sha: SHA of the file to update (for updates).

        Returns:
            Commit details.
        """
        args = {
            "owner": owner,
            "repo": repo,
            "path": path,
            "content": content,
            "message": message,
            "branch": branch,
        }
        if sha:
            args["sha"] = sha
            
        return await self.call_tool("create_or_update_file", args)

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            title: PR title.
            body: PR description.
            head: Head branch.
            base: Base branch.

        Returns:
            Created PR details.
        """
        return await self.call_tool(
            "create_pull_request",
            {
                "owner": owner,
                "repo": repo,
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )

    async def push_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        files: list[dict[str, str]],
        message: str,
    ) -> dict[str, Any]:
        """Push multiple files to a repository in a single commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            branch: Branch name.
            files: List of files with 'path' and 'content' keys.
            message: Commit message.

        Returns:
            Commit details.
        """
        return await self.call_tool(
            "push_files",
            {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "files": files,
                "message": message,
            },
        )
