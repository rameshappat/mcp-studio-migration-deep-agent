"""LangGraph Studio wrapper for SDLC Pipeline with Deep Agents.

This module provides a dynamic, autonomous SDLC pipeline using Deep Agents.
Unlike the fixed graph, agents make their own decisions about flow and routing.

KEY FEATURES:
- Dynamic orchestration (adapts to project complexity)
- Autonomous decision-making (5 decision types)
- Self-correction (automatic validation and fixing)
- Agent spawning (create specialists on demand)
- Confidence-based approval (human-in-loop only when needed)

USAGE IN LANGSMITH STUDIO:
1. Set environment variables in .env
2. Deploy to Studio
3. Start with {"user_query": "your project description"}
4. Agent decides the flow automatically
"""

import os
import logging
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from src.agents.deep_agent import (
    DeepAgent,
    AgentDecision,
    AgentDecisionType,
    ConfidenceLevel,
    ValidationResult,
)

logger = logging.getLogger(__name__)


def reducer(current: list, new: list | None) -> list:
    """Reducer for message lists - appends new messages."""
    if new is None:
        return current
    return current + new


class DeepPipelineState(TypedDict, total=False):
    """State for the Deep Agent SDLC Pipeline."""
    
    # Input
    user_query: str
    project_name: str | None
    
    # Pipeline control
    current_agent: str | None
    orchestrator_decision: dict | None
    pipeline_complete: bool
    
    # Message history
    messages: Annotated[list[dict], reducer]
    
    # Agent outputs (accumulated)
    requirements: dict | None
    work_items: dict | None
    architecture: dict | None
    code_artifacts: dict | None
    
    # External tool results
    ado_results: dict | None
    github_results: dict | None
    mermaid_results: dict | None
    
    # Agent decision history
    decision_history: Annotated[list[dict], reducer]
    
    # Spawned agents tracking
    spawned_agents: list[str] | None
    
    # Confidence and approval
    requires_approval: bool
    approval_reason: str | None
    approval_response: str | None
    
    # Error handling
    errors: list[str]


# ============================================================================
# MCP CLIENT INITIALIZATION
# ============================================================================

_ado_client = None
_github_client = None
_mermaid_client = None


def get_ado_client():
    """Lazily initialize ADO MCP client."""
    global _ado_client
    if _ado_client is None:
        org = os.getenv("AZURE_DEVOPS_ORGANIZATION")
        project = os.getenv("AZURE_DEVOPS_PROJECT")
        if org and project:
            try:
                from src.mcp_client.ado_client import AzureDevOpsMCPClient
                _ado_client = AzureDevOpsMCPClient(
                    organization=org,
                    project=project,
                )
                logger.info(f"ADO client initialized for {org}/{project}")
            except Exception as e:
                logger.warning(f"Could not initialize ADO client: {e}")
    return _ado_client


def get_github_client():
    """Lazily initialize GitHub MCP client."""
    global _github_client
    if _github_client is None:
        mcp_url = os.getenv("GITHUB_MCP_URL")
        token = os.getenv("GITHUB_TOKEN")
        if mcp_url and token:
            try:
                from src.mcp_client.github_client import GitHubMCPClient
                _github_client = GitHubMCPClient(
                    mcp_url=mcp_url,
                    github_token=token,
                )
                logger.info(f"GitHub client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize GitHub client: {e}")
    return _github_client


def get_mermaid_client():
    """Lazily initialize Mermaid MCP client."""
    global _mermaid_client
    if _mermaid_client is None:
        try:
            from src.mcp_client.mermaid_client import MermaidMCPClient
            _mermaid_client = MermaidMCPClient()
            logger.info("Mermaid client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Mermaid client: {e}")
    return _mermaid_client


import asyncio
import functools
import json
from langchain_core.tools import StructuredTool

# Cache for converted LangChain tools
_langchain_tools_cache = None
_tools_initialized = False


async def _initialize_clients():
    """Initialize all MCP clients and their connections."""
    ado = get_ado_client()
    github = get_github_client()
    mermaid = get_mermaid_client()
    
    # Connect to clients that need explicit connection
    if ado:
        try:
            await ado.connect()
            logger.info(f"ADO connected, {len(ado.get_tools())} tools available")
        except Exception as e:
            logger.warning(f"ADO connection failed: {e}")
    
    if github:
        try:
            await github.connect()
            logger.info(f"GitHub connected, {len(github.get_tools())} tools available")
        except Exception as e:
            logger.warning(f"GitHub connection failed: {e}")
    
    if mermaid:
        try:
            await mermaid.connect()
            logger.info(f"Mermaid connected")
        except Exception as e:
            logger.warning(f"Mermaid connection failed: {e}")
    
    return ado, github, mermaid


def _create_langchain_tool(tool_def: dict, client, client_name: str) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition."""
    tool_name = tool_def["name"]
    tool_description = tool_def.get("description", f"Execute {tool_name}")
    
    async def tool_executor(**kwargs) -> str:
        """Execute the MCP tool."""
        try:
            result = await client.call_tool(tool_name, kwargs)
            if isinstance(result, dict):
                return json.dumps(result, indent=2)
            return str(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # Create a sync wrapper that properly handles the async context
    def sync_wrapper(**kwargs) -> str:
        """Sync wrapper for async tool execution."""
        import asyncio
        try:
            # Check if there's a running event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, tool_executor(**kwargs))
                return future.result()
        except RuntimeError:
            # No running event loop, we can use asyncio.run
            return asyncio.run(tool_executor(**kwargs))
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=tool_executor,
        name=f"{client_name}_{tool_name}",
        description=f"[{client_name.upper()}] {tool_description}",
    )


def get_all_tools() -> list:
    """Get all available MCP tools converted to LangChain format.
    
    Returns:
        List of LangChain StructuredTools from all MCP clients.
    """
    global _langchain_tools_cache, _tools_initialized
    
    if _langchain_tools_cache is not None:
        logger.info(f"Returning {len(_langchain_tools_cache)} cached tools")
        return _langchain_tools_cache
    
    logger.info("Building tools from MCP clients...")
    tools = []
    
    # Get clients (they may not be connected yet - that happens in nodes)
    ado = get_ado_client()
    github = get_github_client()
    mermaid = get_mermaid_client()
    
    logger.info(f"Clients available: ADO={ado is not None}, GitHub={github is not None}, Mermaid={mermaid is not None}")
    
    # If clients exist and have tools, convert them
    if ado:
        ado_tools = ado.get_tools()
        logger.info(f"ADO client has {len(ado_tools)} tools")
        for tool_def in ado_tools:
            try:
                lc_tool = _create_langchain_tool(tool_def, ado, "ado")
                tools.append(lc_tool)
            except Exception as e:
                logger.warning(f"Failed to convert ADO tool {tool_def.get('name')}: {e}")
    
    if github:
        gh_tools = github.get_tools()
        logger.info(f"GitHub client has {len(gh_tools)} tools")
        for tool_def in gh_tools:
            try:
                lc_tool = _create_langchain_tool(tool_def, github, "github")
                tools.append(lc_tool)
            except Exception as e:
                logger.warning(f"Failed to convert GitHub tool {tool_def.get('name')}: {e}")
    
    if mermaid:
        mermaid_tools = mermaid.get_tools() if hasattr(mermaid, 'get_tools') else []
        logger.info(f"Mermaid client has {len(mermaid_tools)} tools")
        for tool_def in mermaid_tools:
            try:
                lc_tool = _create_langchain_tool(tool_def, mermaid, "mermaid")
                tools.append(lc_tool)
            except Exception as e:
                logger.warning(f"Failed to convert Mermaid tool {tool_def.get('name')}: {e}")
    
    if tools:
        _langchain_tools_cache = tools
        logger.info(f"Loaded {len(tools)} MCP tools as LangChain tools")
    else:
        logger.warning("No MCP tools available - agents will work with LLM reasoning only")
    
    return tools


async def get_all_tools_async() -> list:
    """Async version that ensures clients are connected first."""
    global _langchain_tools_cache
    
    # Initialize and connect clients
    await _initialize_clients()
    
    # Clear cache to force refresh
    _langchain_tools_cache = None
    
    # Now get tools (clients should be connected)
    return get_all_tools()


# ============================================================================
# AGENT CREATION
# ============================================================================

def create_orchestrator_agent() -> DeepAgent:
    """Create the orchestrator agent that decides the pipeline flow."""
    return DeepAgent(
        role="Orchestrator",
        objective="""Analyze user requirements and orchestrate the SDLC pipeline.
        Decide which agents to invoke and in what order based on project complexity.
        Can skip stages if not needed. Can spawn specialist agents for complex tasks.""",
        system_prompt="""You are the Orchestrator for an autonomous SDLC pipeline.
        
        Your responsibilities:
        1. Analyze the user's project requirements
        2. Decide which stages are needed (requirements, work_items, architecture, code)
        3. Determine if specialists should be spawned
        4. Route to the appropriate next agent
        5. Detect when the pipeline is complete
        
        Decision criteria:
        - Simple projects: Requirements → Code (skip work items and architecture)
        - Moderate projects: Requirements → Architecture → Code
        - Complex projects: Requirements → Work Items → Architecture (spawn specialists) → Code (spawn specialists)
        
        You have access to ALL MCP tools (ADO, GitHub, Mermaid).
        Make autonomous decisions. Request approval only for critical changes.
        """,
        tools=get_all_tools(),
        max_iterations=5,
        confidence_threshold=ConfidenceLevel.MEDIUM,
        enable_spawning=True,
    )


def create_requirements_agent() -> DeepAgent:
    """Create a requirements gathering agent."""
    return DeepAgent(
        role="Requirements Analyst",
        objective="Generate comprehensive software requirements from user descriptions",
        system_prompt="""You are a Requirements Analyst in an SDLC pipeline.
        
        Generate detailed requirements including:
        - Functional requirements
        - Non-functional requirements  
        - User personas
        - Acceptance criteria
        - Technical constraints
        
        Validate your output for completeness. Self-correct if needed.
        Use ADO tools to check existing requirements if available.
        Request approval only if requirements are complex or ambiguous.
        """,
        tools=get_all_tools(),
        max_iterations=5,
        confidence_threshold=ConfidenceLevel.HIGH,
        enable_spawning=False,
    )


def create_work_items_agent() -> DeepAgent:
    """Create a work items agent that creates Epics and Stories in Azure DevOps."""
    return DeepAgent(
        role="Business Analyst",
        objective="Create epics and user stories in Azure DevOps Board",
        system_prompt="""You are a Business Analyst who MUST create work items in Azure DevOps.

YOUR TASK:
1. Analyze the requirements provided
2. Create Epics (high-level features) using the ado_wit_create_work_item tool
3. Create User Stories/Issues for each Epic using the ado_wit_create_work_item tool
4. Add acceptance criteria and story points

CRITICAL: You MUST use the ADO tools to create actual work items. Do NOT just describe them.

TOOL TO USE: ado_wit_create_work_item
Parameters:
- project: "testingmcp" (use this exact project name)
- workItemType: "Epic" or "Issue" (use "Issue" for user stories in Basic process)
- fields: array of {name, value} pairs

EXAMPLE - Create an Epic:
Call ado_wit_create_work_item with:
{
  "project": "testingmcp",
  "workItemType": "Epic",
  "fields": [
    {"name": "System.Title", "value": "User Authentication System"},
    {"name": "System.Description", "value": "Implement complete user authentication including login, registration, and password reset", "format": "Html"}
  ]
}

EXAMPLE - Create a User Story (Issue):
Call ado_wit_create_work_item with:
{
  "project": "testingmcp", 
  "workItemType": "Issue",
  "fields": [
    {"name": "System.Title", "value": "User can login with email and password"},
    {"name": "System.Description", "value": "<b>As a</b> user<br/><b>I want to</b> login with my email and password<br/><b>So that</b> I can access the system<br/><br/><b>Acceptance Criteria:</b><ul><li>Email validation</li><li>Password must be at least 8 characters</li></ul>", "format": "Html"}
  ]
}

WORKFLOW:
1. Call ado_wit_create_work_item to create the FIRST Epic
2. Call ado_wit_create_work_item to create 2-3 Issues for that Epic
3. Call ado_wit_create_work_item to create another Epic if needed
4. Call ado_wit_create_work_item to create Issues for that Epic
5. Summarize what was created with the returned IDs

You MUST make actual tool calls - do not just output text describing work items!
""",
        tools=get_all_tools(),
        max_iterations=10,
        confidence_threshold=ConfidenceLevel.MEDIUM,
        enable_spawning=False,
    )


def create_architecture_agent() -> DeepAgent:

# --- NEW: Test Plan Agent ---
def create_test_plan_agent() -> DeepAgent:
    """Create a test plan agent that creates ADO test plans and test cases."""
    return DeepAgent(
        role="QA Manager",
        objective="Create test plans and test cases in Azure DevOps",
        system_prompt="""You are a QA Manager who MUST create a test plan and test cases in Azure DevOps.

YOUR TASK:
1. Analyze the work items (Epics and Issues) provided
2. Create a Test Plan using the ado_testplan_create_test_plan tool
3. For each Epic/Issue, create a test suite and at least 1-2 test cases using ado_testplan_create_test_suite and ado_testplan_create_test_case

CRITICAL: You MUST use the ADO tools to create actual test plans, suites, and cases. Do NOT just describe them.

TOOLS TO USE:
- ado_testplan_create_test_plan
- ado_testplan_create_test_suite
- ado_testplan_create_test_case

WORKFLOW:
1. Call ado_testplan_create_test_plan for the project 'testingmcp'
2. For each Epic/Issue, call ado_testplan_create_test_suite (parent is root suite)
3. For each suite, call ado_testplan_create_test_case with steps and acceptance criteria
4. Summarize what was created with the returned IDs

You MUST make actual tool calls - do not just output text describing test plans!
""",
        tools=get_all_tools(),
        max_iterations=8,
        confidence_threshold=ConfidenceLevel.MEDIUM,
        enable_spawning=False,
    )


def create_architecture_agent() -> DeepAgent:
    """Create an architecture design agent."""
    return DeepAgent(
        role="Architect",
        objective="Design system architecture and generate diagrams",
        system_prompt="""You are a Software Architect designing system architecture.
        
        Design:
        - High-level architecture
        - Component diagrams
        - Data flow diagrams
        - Technology stack recommendations
        - Deployment architecture
        
        Generate Mermaid diagrams for visualizations.
        Consider:
        - Scalability
        - Security
        - Performance
        - Maintainability
        
        For complex systems, consider spawning specialists:
        - Database Expert
        - API Designer
        - Security Architect
        
        Self-validate architecture decisions.
        """,
        tools=get_all_tools(),
        max_iterations=5,
        confidence_threshold=ConfidenceLevel.MEDIUM,
        enable_spawning=True,
    )


def create_developer_agent() -> DeepAgent:
    """Create a code generation agent that generates production-ready code."""
    return DeepAgent(
        role="Developer",
        objective="Generate production-ready code based on requirements and architecture",
        system_prompt="""You are a Senior Developer who generates production-ready code.

YOUR TASK:
1. Generate complete, working code based on requirements and architecture
2. Include all necessary files: source code, tests, documentation, and configuration

CODE STRUCTURE TO GENERATE:
1. Main application file (src/main.py or src/app.py)
2. Core modules/services (src/*.py)
3. Tests (tests/test_*.py)
4. Configuration (requirements.txt, pyproject.toml)
5. Documentation (README.md)

REQUIREMENTS:
- Generate complete, working code - not just skeleton/stubs
- Include error handling, logging, and proper structure
- Follow best practices for the language/framework
- Include type hints for Python code
- Write comprehensive tests

OUTPUT FORMAT:
For each file, use this format:

### FILE: path/to/file.ext
```language
<complete file contents>
```

Generate ALL files needed for a complete, deployable application.
""",
        tools=get_all_tools(),
        max_iterations=8,
        confidence_threshold=ConfidenceLevel.MEDIUM,
        enable_spawning=False,
    )


# ============================================================================
# GRAPH NODES
# ============================================================================

async def init_node(state: DeepPipelineState) -> dict:
    """Initialize the pipeline and connect to MCP clients."""
    project_name = state.get("project_name", "new-project")
    user_query = state.get("user_query", "")
    
    # Initialize and connect MCP clients
    logger.info("Initializing MCP clients...")
    await _initialize_clients()
    
    # Load tools after clients are connected
    tools = await get_all_tools_async()
    tool_count = len(tools)
    
    # Get client status
    ado = get_ado_client()
    github = get_github_client()
    mermaid = get_mermaid_client()
    
    clients_status = {
        "ado": ado is not None and len(ado.get_tools()) > 0 if ado else False,
        "github": github is not None and len(github.get_tools()) > 0 if github else False,
        "mermaid": mermaid is not None,
    }
    
    logger.info(f"MCP clients initialized. Tools available: {tool_count}")
    logger.info(f"Client status: ADO={clients_status['ado']}, GitHub={clients_status['github']}, Mermaid={clients_status['mermaid']}")
    
    return {
        "messages": [{
            "role": "system",
            "content": f"🚀 Initializing SDLC Pipeline for: {project_name}",
            "mcp_tools": tool_count,
            "clients": clients_status,
        }],
        "errors": [],
    }


async def orchestrator_node(state: DeepPipelineState) -> dict:
    """Orchestrator decides the pipeline flow using deterministic logic."""
    
    user_query = state.get("user_query", "")
    
    # Check what's already completed
    has_requirements = state.get("requirements") is not None
    has_work_items = state.get("work_items") is not None
    has_architecture = state.get("architecture") is not None
    has_code = state.get("code_artifacts") is not None
    

    # New: Add test_plan step after work_items
    has_test_plan = state.get("test_plan") is not None

    # New flow: requirements → work_items → test_plan → architecture → development
    if not has_requirements:
        next_agent = "requirements"
        reasoning = "Starting with requirements gathering"
    elif not has_work_items:
        next_agent = "work_items"
        reasoning = "Requirements done, creating work items in ADO"
    elif not has_test_plan:
        next_agent = "test_plan"
        reasoning = "Work items created, now creating ADO test plan and test cases"
    elif not has_architecture:
        next_agent = "architecture"
        reasoning = "Test plan created, moving to architecture design"
    elif not has_code:
        next_agent = "development"
        reasoning = "Architecture done, moving to code generation and GitHub push"
    else:
        next_agent = "complete"
        reasoning = "All stages complete!"
    
    logger.info(f"Orchestrator decision: {next_agent} - {reasoning}")
    
    return {
        "current_agent": next_agent,
        "orchestrator_decision": {
            "next_agent": next_agent,
            "reasoning": reasoning,
            "confidence": "high",
        },
        "requires_approval": False,  # Orchestrator doesn't need approval for routing
        "messages": [{
            "role": "orchestrator",
            "content": f"🎯 Orchestrator Decision: Route to {next_agent}",
            "reasoning": reasoning,
            "confidence": "high",
        }],
        "decision_history": [{
            "agent": "orchestrator",
            "decision": next_agent,
            "confidence": "high",
        }],
    }


async def requirements_agent_node(state: DeepPipelineState) -> dict:
    """Requirements agent generates requirements."""
    agent = create_requirements_agent()
    
    user_query = state.get("user_query", "")
    task = f"Generate comprehensive requirements for: {user_query}"
    
    try:
        result = await agent.execute(task)
        
        # Parse requirements from output - result is a dict
        output = result.get("output", "")
        decision_info = result.get("decision", {})
        confidence = decision_info.get("confidence", "medium")
        decision_type = decision_info.get("type", "complete")
        iterations = result.get("iterations", 1)
        
        requirements = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
        }
        
        requires_approval = decision_type == "request_approval"
        
        return {
            "requirements": requirements,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "requirements_analyst",
                "content": "📋 Requirements generated",
                "details": output[:500] if output else "",
                "confidence": confidence,
            }],
            "decision_history": [{
                "agent": "requirements",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"Requirements agent failed: {e}")
        return {
            "errors": [f"Requirements error: {str(e)}"],
        }


async def work_items_agent_node(state: DeepPipelineState) -> dict:
    """Work items agent creates epics and user stories in Azure DevOps."""
    agent = create_work_items_agent()
    
    requirements = state.get("requirements", {})
    project_name = state.get("project_name", "new-project")
    
    task = f"""Create work items (Epics and User Stories/Issues) in Azure DevOps for project: {project_name}

REQUIREMENTS:
{requirements.get('description', 'No requirements available')}

IMPORTANT: You MUST use the ado_wit_create_work_item tool to create actual work items in ADO.
The project name in ADO is 'testingmcp'. Create at least:
- 1-2 Epics for major features
- 3-5 Issues (user stories) per Epic

Call the tool for EACH work item you want to create.
"""
    
    try:
        result = await agent.execute(task)
        
        # Parse work items from output - result is a dict
        output = result.get("output", "")
        decision_info = result.get("decision", {})
        confidence = decision_info.get("confidence", "medium")
        decision_type = decision_info.get("type", "complete")
        iterations = result.get("iterations", 1)
        tool_calls_made = result.get("tool_calls_made", 0)
        
        work_items = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "tool_calls_made": tool_calls_made,
        }
        
        requires_approval = decision_type == "request_approval"
        
        # Check if tools were actually called
        if tool_calls_made == 0:
            logger.warning("Work items agent did not call any ADO tools!")
        
        return {
            "work_items": work_items,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "business_analyst",
                "content": f"📊 Work items created (tool calls: {tool_calls_made})",
                "details": output[:500] if output else "",
                "confidence": confidence,
            }],
            "decision_history": [{
                "agent": "work_items",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"Work items agent failed: {e}")
        return {
            "errors": [f"Work items error: {str(e)}"],
        }



# --- NEW: Test Plan Agent Node ---
async def test_plan_agent_node(state: DeepPipelineState) -> dict:
    """Test plan agent creates ADO test plans, suites, and test cases."""
    agent = create_test_plan_agent()
    work_items = state.get("work_items", {})
    project_name = state.get("project_name", "new-project")

    task = f"""Create a test plan and test cases in Azure DevOps for project: {project_name}

WORK ITEMS:
{work_items.get('description', 'No work items available')}

IMPORTANT: You MUST use the ado_testplan_create_test_plan, ado_testplan_create_test_suite, and ado_testplan_create_test_case tools to create actual test plans and cases in ADO.
The project name in ADO is 'testingmcp'.
"""
    try:
        result = await agent.execute(task)
        output = result.get("output", "")
        decision_info = result.get("decision", {})
        confidence = decision_info.get("confidence", "medium")
        decision_type = decision_info.get("type", "complete")
        iterations = result.get("iterations", 1)
        tool_calls_made = result.get("tool_calls_made", 0)

        test_plan = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "tool_calls_made": tool_calls_made,
        }

        requires_approval = decision_type == "request_approval"

        if tool_calls_made == 0:
            logger.warning("Test plan agent did not call any ADO test plan tools!")

        return {
            "test_plan": test_plan,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "qa_manager",
                "content": f"🧪 Test plan created (tool calls: {tool_calls_made})",
                "details": output[:500] if output else "",
                "confidence": confidence,
            }],
            "decision_history": [{
                "agent": "test_plan",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"Test plan agent failed: {e}")
        return {
            "errors": [f"Test plan error: {str(e)}"],
        }


# --- Existing: Architecture Agent Node ---
async def architecture_agent_node(state: DeepPipelineState) -> dict:
    """Architecture agent designs system architecture."""
    agent = create_architecture_agent()
    
    requirements = state.get("requirements", {})
    work_items = state.get("work_items", {})
    test_plan = state.get("test_plan", {})
    
    task = f"""Design system architecture for:

Requirements:
{requirements.get('description', 'No requirements')}

Work Items:
{work_items.get('description', 'No work items') if work_items else 'Skipped'}

Test Plan:
{test_plan.get('description', 'No test plan') if test_plan else 'Skipped'}

Generate:
1. High-level architecture
2. Component diagrams (use Mermaid MCP tools)
3. Technology stack recommendations
4. Deployment architecture

For complex systems, spawn specialist sub-agents if needed.
"""
    try:
        result = await agent.execute(task)
        
        # Parse architecture from output - result is a dict
        output = result.get("output", "")
        decision_info = result.get("decision", {})
        confidence = decision_info.get("confidence", "medium")
        decision_type = decision_info.get("type", "complete")
        iterations = result.get("iterations", 1)
        spawned_count = result.get("spawned_agents", 0)
        
        architecture = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "spawned_agents": spawned_count,
        }
        
        requires_approval = decision_type == "request_approval"
        
        return {
            "architecture": architecture,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "architect",
                "content": "🏗️ Architecture designed",
                "details": output[:500] if output else "",
                "confidence": confidence,
                "spawned": spawned_count,
            }],
            "decision_history": [{
                "agent": "architecture",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"Architecture agent failed: {e}")
        return {
            "errors": [f"Architecture error: {str(e)}"],
        }


async def developer_agent_node(state: DeepPipelineState) -> dict:
    """Developer agent generates code."""
    agent = create_developer_agent()
    
    requirements = state.get("requirements", {})
    architecture = state.get("architecture", {})
    
    task = f"""Generate production-ready code for:

Requirements:
{requirements.get('description', 'No requirements')}

Architecture:
{architecture.get('description', 'No architecture') if architecture else 'No formal architecture'}

Generate:
1. Complete, working code
2. Unit tests
3. Documentation
4. README
5. Configuration files

Use GitHub MCP tools to:
1. Create repository structure
2. Commit code
3. Create pull request

For large projects, spawn specialist developers (frontend, backend, testing, devops).
"""
    
    try:
        result = await agent.execute(task)
        
        # Parse code artifacts from output - result is a dict
        output = result.get("output", "")
        decision_info = result.get("decision", {})
        confidence = decision_info.get("confidence", "medium")
        decision_type = decision_info.get("type", "complete")
        iterations = result.get("iterations", 1)
        spawned_count = result.get("spawned_agents", 0)
        
        code_artifacts = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "spawned_agents": spawned_count,
        }
        
        requires_approval = decision_type == "request_approval"
        
        return {
            "code_artifacts": code_artifacts,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "developer",
                "content": "💻 Code generated",
                "details": output[:500] if output else "",
                "confidence": confidence,
                "spawned": spawned_count,
            }],
            "decision_history": [{
                "agent": "development",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"Developer agent failed: {e}")
        return {
            "errors": [f"Development error: {str(e)}"],
        }


async def approval_node(state: DeepPipelineState) -> dict:
    """Human approval checkpoint (only invoked if needed)."""
    approval_reason = state.get("approval_reason", "Agent requested approval")
    current_agent = state.get("current_agent", "unknown")
    
    response = interrupt({
        "type": "approval",
        "agent": current_agent,
        "message": f"🤔 Agent requests approval",
        "reason": approval_reason,
        "instructions": "Type 'approve' to continue or 'revise' to regenerate",
    })
    
    return {
        "approval_response": response,
        "requires_approval": False,  # Clear the flag
        "messages": [{
            "role": "human",
            "content": f"User: {response}",
        }],
    }


async def complete_node(state: DeepPipelineState) -> dict:
    """Mark pipeline as complete."""
    return {
        "pipeline_complete": True,
        "messages": [{
            "role": "system",
            "content": "✅ SDLC Pipeline Complete!",
        }],
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_from_orchestrator(state: DeepPipelineState) -> str:
    """Route based on orchestrator's decision."""
    if state.get("requires_approval"):
        return "approval"
    
    next_agent = state.get("current_agent", "requirements")
    
    if next_agent == "complete":
        return "complete"
    
    return next_agent


def route_after_agent(state: DeepPipelineState) -> str:
    """Route after an agent completes its work."""
    if state.get("requires_approval"):
        return "approval"
    
    # Go back to orchestrator to decide next step
    return "orchestrator"


def route_after_approval(state: DeepPipelineState) -> str:
    """Route after human approval."""
    response = str(state.get("approval_response", "")).lower().strip()
    current_agent = state.get("current_agent", "orchestrator")
    
    if response in ("approve", "approved", "yes", "y", "ok", "continue"):
        # Continue to orchestrator for next decision
        return "orchestrator"
    else:
        # Retry current agent
        return current_agent


# ============================================================================
# GRAPH BUILDER
# ============================================================================

def build_graph():
    """Build the autonomous SDLC Pipeline graph."""
    
    builder = StateGraph(DeepPipelineState)
    
    # Add nodes
    builder.add_node("init", init_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("requirements", requirements_agent_node)
    builder.add_node("work_items", work_items_agent_node)
    builder.add_node("test_plan", test_plan_agent_node)
    builder.add_node("architecture", architecture_agent_node)
    builder.add_node("development", developer_agent_node)
    builder.add_node("approval", approval_node)
    builder.add_node("complete", complete_node)
    
    # Start -> Init -> Orchestrator
    builder.add_edge(START, "init")
    builder.add_edge("init", "orchestrator")
    
    # Orchestrator routes to agents or complete
    builder.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "requirements": "requirements",
            "work_items": "work_items",
            "test_plan": "test_plan",
            "architecture": "architecture",
            "development": "development",
            "approval": "approval",
            "complete": "complete",
        }
    )
    
    # Agents return to orchestrator (or approval)
    for agent in ["requirements", "work_items", "test_plan", "architecture", "development"]:
        builder.add_conditional_edges(
            agent,
            route_after_agent,
            {
                "orchestrator": "orchestrator",
                "approval": "approval",
            }
        )
    
    # Approval routes back to orchestrator or retry agent
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "orchestrator": "orchestrator",
            "requirements": "requirements",
            "work_items": "work_items",
            "architecture": "architecture",
            "development": "development",
        }
    )
    
    # Complete -> END
    builder.add_edge("complete", END)
    
    # Compile with interrupt at approval
    return builder.compile(
        interrupt_before=["approval"]
    )


# Export the compiled graph for LangGraph Studio
graph = build_graph()
