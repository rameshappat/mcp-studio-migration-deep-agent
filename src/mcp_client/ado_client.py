"""Azure DevOps MCP Client for connecting to the Azure DevOps MCP Server via stdio."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class AzureDevOpsMCPClient:
    """Client for interacting with Azure DevOps via MCP Server (stdio).
    
    Uses the @azure-devops/mcp npm package via stdio transport.
    """

    def __init__(
        self,
        organization: str,
        project: str | None = None,
        domains: list[str] | None = None,
        auth_type: str = "interactive",
    ):
        """Initialize the Azure DevOps MCP Client.

        Args:
            organization: Azure DevOps organization name.
            project: Azure DevOps project name (optional).
            domains: List of domains to enable (e.g., ["core", "work", "work-items"]).
            auth_type: Authentication type ("interactive", "azcli", "env", "envvar").
        """
        self.organization = organization
        self.project = project
        self.domains = domains or ["core", "work", "work-items", "test-plans"]
        self.auth_type = auth_type
        self._tools: list[dict] = []
        self._connected = False
        self._pat: str = ""
        
        # Map various PAT env var names to ADO_MCP_AUTH_TOKEN for the MCP server
        pat = os.environ.get("ADO_MCP_AUTH_TOKEN") or os.environ.get("AZURE_DEVOPS_EXT_PAT") or os.environ.get("AZURE_DEVOPS_PAT", "")
        if pat:
            self._pat = pat
            os.environ["ADO_MCP_AUTH_TOKEN"] = pat
            # Auto-switch to envvar auth if PAT is available and auth_type is default
            if self.auth_type == "interactive":
                self.auth_type = "envvar"

    def _get_server_params(self) -> StdioServerParameters:
        """Get stdio server parameters for the ADO MCP server."""
        args = ["-y", "@azure-devops/mcp", self.organization, "-a", self.auth_type, "-d"] + self.domains
        
        # Build environment with PAT for envvar auth
        env = {**os.environ}
        if self._pat:
            env["ADO_MCP_AUTH_TOKEN"] = self._pat
        
        return StdioServerParameters(
            command="npx",
            args=args,
            env=env,
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
        """Test connection to the Azure DevOps MCP server and list tools."""
        logger.info(f"Connecting to Azure DevOps MCP server for org: {self.organization}")

        try:
            async with self._get_session() as session:
                # List available tools
                tools_result = await session.list_tools()
                self._tools = [
                    {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
                    for tool in tools_result.tools
                ]
                self._connected = True
                
                logger.info(f"Connected! Found {len(self._tools)} ADO tools")
                print(f"✅ Connected to Azure DevOps MCP ({self.organization}). Found {len(self._tools)} tools.")
        except Exception as e:
            logger.error(f"Failed to connect to Azure DevOps MCP: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close the connection (no-op for session-per-call model)."""
        self._connected = False
        logger.info("Azure DevOps MCP connection closed")

    def get_tools(self) -> list[dict]:
        """Get list of available tools."""
        return self._tools

    def get_tool_names(self) -> list[str]:
        """Get list of available tool names."""
        return [tool["name"] for tool in self._tools]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the Azure DevOps MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The result from the tool execution.
        """
        # Add project to arguments if not present and we have one
        if "project" not in arguments and self.project:
            arguments["project"] = self.project

        logger.info(f"Calling ADO tool: {tool_name}")

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

    async def create_work_item(
        self,
        work_item_type: str,
        title: str,
        description: str = "",
        project: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a work item in Azure DevOps.

        Args:
            work_item_type: Type of work item (Epic, Feature, User Story, Task, Bug).
            title: Title of the work item.
            description: Description of the work item.
            project: Project name (uses default if not specified).
            **kwargs: Additional fields.

        Returns:
            Created work item details.
        """
        return await self.call_tool(
            "mcp_ado_wit_create_work_item",
            {
                "project": project or self.project,
                "type": work_item_type,
                "title": title,
                "description": description,
                **kwargs,
            },
        )

    async def update_work_item(
        self,
        work_item_id: int,
        **fields: Any,
    ) -> dict[str, Any]:
        """Update a work item in Azure DevOps.

        Args:
            work_item_id: ID of the work item to update.
            **fields: Fields to update.

        Returns:
            Updated work item details.
        """
        return await self.call_tool(
            "mcp_ado_wit_update_work_item",
            {
                "workItemId": work_item_id,
                **fields,
            },
        )

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        """Get a work item from Azure DevOps.

        Args:
            work_item_id: ID of the work item.

        Returns:
            Work item details.
        """
        return await self.call_tool(
            "mcp_ado_wit_get_work_item",
            {"workItemId": work_item_id},
        )

    async def query_work_items(self, wiql: str) -> list[dict[str, Any]]:
        """Query work items using WIQL.

        Args:
            wiql: Work Item Query Language query.

        Returns:
            List of matching work items.
        """
        return await self.call_tool(
            "mcp_ado_wit_query",
            {"query": wiql},
        )

    async def add_work_item_link(
        self,
        source_id: int,
        target_id: int,
        link_type: str = "System.LinkTypes.Hierarchy-Forward",
    ) -> dict[str, Any]:
        """Add a link between work items.

        Args:
            source_id: Source work item ID.
            target_id: Target work item ID.
            link_type: Type of link.

        Returns:
            Link creation result.
        """
        return await self.call_tool(
            "mcp_ado_wit_add_link",
            {
                "workItemId": source_id,
                "targetId": target_id,
                "linkType": link_type,
            },
        )

    async def create_epic(
        self,
        title: str,
        description: str,
        acceptance_criteria: list[str] | None = None,
        business_value: str = "",
    ) -> dict[str, Any]:
        """Create an Epic in Azure DevOps.

        Args:
            title: Epic title.
            description: Epic description.
            acceptance_criteria: List of acceptance criteria.
            business_value: Business value statement.

        Returns:
            Created Epic details.
        """
        full_description = description
        if acceptance_criteria:
            full_description += "\n\n**Acceptance Criteria:**\n"
            full_description += "\n".join(f"- {ac}" for ac in acceptance_criteria)
        if business_value:
            full_description += f"\n\n**Business Value:**\n{business_value}"

        return await self.create_work_item("Epic", title, full_description)

    async def create_user_story(
        self,
        title: str,
        description: str,
        acceptance_criteria: list[str] | None = None,
        story_points: int | None = None,
        priority: int = 2,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a User Story in Azure DevOps.

        Args:
            title: Story title (preferably in "As a... I want... So that..." format).
            description: Story description.
            acceptance_criteria: Acceptance criteria in Gherkin format.
            story_points: Story points estimate.
            priority: Priority (1=highest, 4=lowest).
            parent_id: Parent Epic ID.

        Returns:
            Created User Story details.
        """
        full_description = description
        if acceptance_criteria:
            full_description += "\n\n**Acceptance Criteria:**\n"
            full_description += "\n".join(f"- {ac}" for ac in acceptance_criteria)

        kwargs = {"priority": priority}
        if story_points:
            kwargs["storyPoints"] = story_points

        result = await self.create_work_item("User Story", title, full_description, **kwargs)

        # Link to parent Epic if provided
        if parent_id and "id" in result:
            await self.add_work_item_link(parent_id, result["id"])

        return result

    async def create_task(
        self,
        title: str,
        description: str,
        remaining_work: float | None = None,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a Task in Azure DevOps.

        Args:
            title: Task title.
            description: Task description.
            remaining_work: Estimated hours.
            parent_id: Parent Story ID.

        Returns:
            Created Task details.
        """
        kwargs = {}
        if remaining_work:
            kwargs["remainingWork"] = remaining_work

        result = await self.create_work_item("Task", title, description, **kwargs)

        # Link to parent Story if provided
        if parent_id and "id" in result:
            await self.add_work_item_link(parent_id, result["id"])

        return result

    def get_tool_names(self) -> list[str]:
        """Get list of available tool names."""
        return [tool.get("name", "") for tool in self._tools]
