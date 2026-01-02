"""Convert MCP tools to LangChain tools."""

import json
from typing import Any, Callable

from langchain_core.tools import StructuredTool
from mcp.types import Tool as MCPTool


def mcp_tools_to_langchain(
    mcp_tools: list[MCPTool],
    tool_executor: Callable[[str, dict[str, Any]], Any],
) -> list[StructuredTool]:
    """Convert MCP tools to LangChain StructuredTools.

    Args:
        mcp_tools: List of MCP tools to convert.
        tool_executor: Async function to execute MCP tool calls.

    Returns:
        List of LangChain StructuredTools.
    """
    langchain_tools = []

    for mcp_tool in mcp_tools:
        # Create a closure to capture the tool name
        def create_tool_func(tool_name: str):
            async def tool_func(**kwargs: Any) -> str:
                """Execute the MCP tool."""
                result = await tool_executor(tool_name, kwargs)
                if isinstance(result, dict):
                    return json.dumps(result, indent=2)
                return str(result)

            return tool_func

        # Build the tool schema from MCP input schema
        schema = mcp_tool.inputSchema if mcp_tool.inputSchema else {}

        tool = StructuredTool.from_function(
            coroutine=create_tool_func(mcp_tool.name),
            name=mcp_tool.name,
            description=mcp_tool.description or f"Execute {mcp_tool.name}",
            args_schema=None,  # Let it infer from the function
        )

        langchain_tools.append(tool)

    return langchain_tools


def format_tool_for_display(mcp_tool: MCPTool) -> str:
    """Format an MCP tool for display purposes."""
    schema = mcp_tool.inputSchema or {}
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    params = []
    for name, prop in properties.items():
        param_type = prop.get("type", "any")
        is_required = name in required
        req_str = " (required)" if is_required else ""
        params.append(f"  - {name}: {param_type}{req_str}")

    param_str = "\n".join(params) if params else "  No parameters"

    return f"""Tool: {mcp_tool.name}
Description: {mcp_tool.description or 'No description'}
Parameters:
{param_str}
"""
