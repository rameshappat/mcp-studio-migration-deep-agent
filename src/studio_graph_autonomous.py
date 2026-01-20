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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    test_plan: dict | None
    test_plan_complete: bool
    test_cases: list | None
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
    consecutive_failures: dict[str, int] | None  # Track failures per agent


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
    """Create a requirements gathering agent (optimized for demo)."""
    return DeepAgent(
        role="Requirements Analyst",
        objective="Generate comprehensive software requirements quickly",
        system_prompt="""You are a Requirements Analyst in an SDLC pipeline.

DEMO MODE: Be concise and complete in 1 iteration.

Generate a complete requirements document including:
- Functional requirements (3-5 key features)
- Non-functional requirements (performance, security, scalability)
- User personas (1-2 main personas)
- Acceptance criteria
- Technical constraints

Be thorough but concise. Complete in a single response without multiple validation rounds.
        """,
        tools=get_all_tools(),
        max_iterations=2,  # Reduced from 5
        confidence_threshold=ConfidenceLevel.MEDIUM,  # Lowered threshold
        enable_spawning=False,
    )


def create_work_items_agent() -> DeepAgent:
    """Create a work items agent that creates comprehensive epics and stories."""
    return DeepAgent(
        role="Business Analyst",
        objective="Create comprehensive epics and user stories in Azure DevOps",
        system_prompt="""You are a Business Analyst creating work items in Azure DevOps.

⚠️ MANDATORY: CALL TOOLS IN YOUR FIRST RESPONSE!

YOUR TASK:
1. Create 1-2 Epics (high-level features) using ado_wit_create_work_item
2. Create 6-8 Issues/Stories (detailed user stories) using ado_wit_create_work_item
3. Make stories SPECIFIC and detailed, covering different aspects:
   - User interface/frontend features
   - Backend API endpoints
   - Database/data management
   - Security/authentication
   - Integration with external services
   - Testing/quality requirements
   - DevOps/deployment
   - Documentation

TOOL: ado_wit_create_work_item
Parameters:
- project: "testingmcp"
- workItemType: "Epic" or "Issue"
- fields: [{"name": "System.Title", "value": "Descriptive title"}, {"name": "System.Description", "value": "Detailed description with acceptance criteria"}]

QUALITY: Each work item should have:
- Clear, specific title (not generic)
- Detailed description explaining the feature
- Acceptance criteria when applicable

START CALLING ado_wit_create_work_item NOW - CREATE 7-10 WORK ITEMS TOTAL!
""",
        tools=get_all_tools(),
        max_iterations=8,  # Increased for more work items
        confidence_threshold=ConfidenceLevel.LOW,  # Lower to force more work
        enable_spawning=False,
    )



# --- NEW: Test Plan Agent ---
def create_test_plan_agent() -> DeepAgent:
    """Create a test plan agent that creates ADO test cases."""
    return DeepAgent(
        role="QA Manager",
        objective="Create comprehensive test cases in Azure DevOps based on requirements",
        system_prompt="""You are a Senior QA Manager. You MUST use tools to create test cases.

⚠️ MANDATORY: CALL TOOLS IN YOUR FIRST RESPONSE - DO NOT WAIT!

EXACT TOOL CALL SEQUENCE (execute for EACH work item):
1. First, call: testplan_create_test_case
   Parameters:
   - project: (the project name provided)
   - title: "Test: [exact work item title]"
   - steps: "1. Detailed action|Expected result\\n2. Next action|Expected result\\n3. Action|Result\\n4. Action|Result\\n5. Action|Result\\n6. Action|Result"

2. Then, call: testplan_add_test_cases_to_suite
   Parameters:
   - project: (same project)
   - test_plan_id: (provided plan ID)
   - test_suite_id: (provided suite ID)
   - test_case_ids: [<ID from step 1>]

QUALITY: Each test case needs 4-6 detailed steps with SPECIFIC actions and expected results.

Example good steps:
"1. Navigate to /register page and verify form displays|Registration form shows with email, password, confirm fields and submit button
2. Enter email 'user@test.com' and password 'Pass123!'|Fields accept input, no validation errors shown
3. Enter different password in confirm field|Red error message: 'Passwords do not match'
4. Correct confirm password to match and click Submit|Loading indicator shows, form disabled
5. Check email inbox for verification message|Email arrives within 30 seconds with subject 'Verify Account'
6. Click verification link and verify redirect|Redirects to /verified page with success message"

YOU MUST CALL TOOLS - NO PLANNING, NO EXPLANATION, JUST EXECUTE NOW!
""",
        tools=get_all_tools(),
        max_iterations=12,
        confidence_threshold=ConfidenceLevel.LOW,
        enable_spawning=False,
    )


def create_architecture_agent() -> DeepAgent:
    """Create an architecture design agent (optimized for demo)."""
    return DeepAgent(
        role="Architect",
        objective="Design system architecture quickly and efficiently",
        system_prompt="""You are a Software Architect designing system architecture.

DEMO MODE: Complete in ONE response. Be concise.

Generate:
1. One paragraph architecture summary
2. ONE Mermaid diagram (Azure + React + Spring Boot)

Use Northern Trust standards: Azure services, React JS, Java Spring Boot, OAuth 2.0.

OUTPUT: Brief summary + diagram. Done.
One brief paragraph + ONE Mermaid diagram. Complete in ONE response.
        """,
        tools=get_all_tools(),
        max_iterations=1,  # DEMO: Single iteration only
        confidence_threshold=ConfidenceLevel.LOW,
        enable_spawning=False,
    )


def create_developer_agent() -> DeepAgent:
    """Create a code generation agent (optimized for demo)."""
    return DeepAgent(
        role="Developer",
        objective="Generate production-ready code quickly for demo",
        system_prompt="""You are a Senior Developer who generates production-ready code.

SINGLE-PASS MODE: Generate complete code in ONE response.

CRITICAL RULES:
1. DO NOT call any tools (no ADO, no GitHub, no external calls)
2. Generate ALL files directly in your response
3. Decide COMPLETE immediately after generating files

YOUR TASK:
Generate 6-8 quality files in ONE shot:
1. README.md - Professional setup & usage instructions
2. src/main.py or src/app.py - Well-structured main application
3. src/config.py - Configuration management
4. src/models.py or src/entities.py - Data models/classes
5. src/utils.py or src/helpers.py - Utility functions
6. requirements.txt or package.json - Complete dependencies
7. tests/test_main.py - Comprehensive test cases
8. .env.example - Environment variables template

OUTPUT FORMAT (CRITICAL):
### FILE: path/to/file.ext
```language
<complete file contents>
```

Generate ALL files, then decide: COMPLETE
""",
        tools=[],  # NO TOOLS - just generate code directly
        max_iterations=1,  # Single iteration only - generate all files at once
        confidence_threshold=ConfidenceLevel.LOW,  # Lower threshold
        enable_spawning=False,
    )


def create_github_integration_agent() -> DeepAgent:
    """Create GitHub Integration agent for repository management with LLM-driven tool decisions."""
    return DeepAgent(
        role="GitHub Integration Specialist",
        objective="Create GitHub repository, push code files, and create pull request using best practices",
        system_prompt="""You are a DevOps Engineer specializing in GitHub repository management.

YOUR TASK:
1. Create a GitHub repository (if repository already exists, note it and continue)
2. Create a feature branch 'feature/initial-implementation' from 'main' (if fails, use 'main' directly)
3. Parse generated code files and push them to GitHub
4. Create a pull request with proper description

AVAILABLE GITHUB TOOLS:
- create_repository: Creates a new GitHub repository
- create_branch: Creates a new branch from an existing branch
- create_or_update_file: Creates or updates a file in the repository (content must be base64-encoded!)
- create_pull_request: Creates a pull request

CODE FILE PARSING:
Files are in format:
### FILE: path/to/file.ext
```language
file contents here
```

CRITICAL NOTES:
- When using create_or_update_file, the 'content' parameter MUST be base64-encoded
- Handle errors gracefully - if repo exists or branch exists, continue with next steps
- Always report the repository URL and PR URL in your final output
- Use GitHub MCP tools to accomplish tasks - don't describe, just do it!
""",
        tools=get_all_tools(),  # Has access to all GitHub MCP tools
        max_iterations=5,
        confidence_threshold=ConfidenceLevel.LOW,
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
    
    # CRITICAL: Clear all previous pipeline state to ensure fresh run
    return {
        "messages": [{
            "role": "system",
            "content": f"🚀 Initializing SDLC Pipeline for: {project_name}",
            "mcp_tools": tool_count,
            "clients": clients_status,
        }],
        "errors": [],
        # Explicitly clear all pipeline outputs from previous runs
        "requirements": None,
        "work_items": None,
        "test_plan": None,
        "test_plan_complete": False,
        "test_cases": None,
        "architecture": None,
        "code_artifacts": None,
        "pipeline_complete": False,
        "requires_approval": False,
        "consecutive_failures": {},  # Initialize failure tracking
    }


async def orchestrator_node(state: DeepPipelineState) -> dict:
    """Orchestrator decides the pipeline flow using deterministic logic."""
    
    user_query = state.get("user_query", "")
    
    # Check what's already completed
    has_requirements = state.get("requirements") is not None
    has_work_items = state.get("work_items") is not None
    has_architecture = state.get("architecture") is not None
    has_code = state.get("code_artifacts") is not None
    

    # Check if test plan is complete (only check the completion flag)
    has_test_plan = state.get("test_plan_complete", False)

    # DEBUG: Log current state flags
    logger.info(f"🔍 Orchestrator State Check:")
    logger.info(f"  has_requirements: {has_requirements}")
    logger.info(f"  has_work_items: {has_work_items}")
    logger.info(f"  has_test_plan: {has_test_plan}")
    logger.info(f"  has_architecture: {has_architecture}")
    logger.info(f"  has_code: {has_code}")

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
    
    logger.info(f"🎯 Orchestrator decision: {next_agent} - {reasoning}")
    
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
        tool_calls = result.get("tool_calls", [])
        
        # CHECK FOR TOOL FAILURES
        failed_tool_calls = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool", "")
            tool_result = tool_call.get("result", {})
            
            if isinstance(tool_result, dict):
                if "text" in tool_result and "error" in tool_result["text"].lower():
                    logger.error(f"❌ MCP TOOL ERROR in requirements_agent: {tool_name}")
                    logger.error(f"   Error: {tool_result['text'][:200]}")
                    logger.error(f"   Args: {tool_call.get('args', {})}")
                    failed_tool_calls.append({
                        "tool": tool_name,
                        "error": tool_result["text"],
                        "args": tool_call.get("args", {})
                    })
        
        if failed_tool_calls:
            logger.warning(f"⚠️  Requirements agent had {len(failed_tool_calls)} failed tool calls")
        
        requirements = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "failed_tool_calls": failed_tool_calls,
        }
        
        # Human-in-the-loop: Request approval if agent decides it needs review
        requires_approval = decision_type == "request_approval"
        
        return {
            "requirements": requirements,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "requirements_analyst",
                "content": "📋 Requirements generated" + (f" ({len(failed_tool_calls)} tool calls failed)" if failed_tool_calls else ""),
                "details": output[:500] if output else "",
                "confidence": confidence,
            }],
            "decision_history": [{
                "agent": "requirements",
                "decision": decision_type,
                "confidence": confidence,
                "failed_tools": len(failed_tool_calls),
            }],
        }
    except Exception as e:
        logger.error(f"❌ EXCEPTION in requirements_agent_node: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        
        # Log full traceback
        import traceback
        logger.error("   Full traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                logger.error(f"   {line}")
        
        return {
            "errors": [f"Requirements error: {str(e)}"],
            "exception_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "requirements": {
                "description": f"Failed: {str(e)}",
                "confidence": "low",
            },
        }


async def work_items_agent_node(state: DeepPipelineState) -> dict:
    """Work items agent creates epics and user stories in Azure DevOps."""
    agent = create_work_items_agent()
    
    requirements = state.get("requirements", {})
    user_query = state.get("user_query", "")
    
    task = f"""Create COMPREHENSIVE, DETAILED work items in Azure DevOps for this project.

PROJECT: testingmcp

REQUIREMENTS:
{requirements.get('description', 'No requirements available')}

USER REQUEST:
{user_query}

⚠️ CRITICAL INSTRUCTIONS:

1. CREATE 7-10 WORK ITEMS using ado_wit_create_work_item tool
2. Each work item MUST include ALL required fields:
   - project: "testingmcp"
   - title: SPECIFIC, DETAILED title (not generic)
   - workItemType: "Epic" or "Issue"
   - description: DETAILED description with acceptance criteria
   - tags: relevant tags (e.g., "frontend", "backend", "security")

3. WORK ITEM CATEGORIES TO CREATE:

EPICS (create 1-2 high-level features):
   Example:
   - Title: "Wealth Management Client Onboarding System"
   - Description: "Complete onboarding flow for new wealth management clients including KYC/AML verification, account setup, and initial portfolio configuration."
   - Type: Epic

ISSUES/STORIES (create 6-8 specific features):
   a) Frontend/UI:
      - Title: "React Client Dashboard with Account Summary and Portfolio View"
      - Description: "Create responsive React dashboard showing client account summary, portfolio holdings, performance charts, and transaction history. Must support OAuth 2.0 authentication."
   
   b) Backend API:
      - Title: "Spring Boot REST API for Client Profile Management"
      - Description: "Implement RESTful endpoints for CRUD operations on client profiles, including GET /clients, POST /clients, PUT /clients/{{id}}, DELETE /clients/{{id}}. Must integrate with Azure SQL Database."
   
   c) Authentication & Security:
      - Title: "OAuth 2.0 Authentication Server Integration"
      - Description: "Integrate with OAuth 2.0 authorization server for secure token-based authentication. Implement JWT token validation middleware in Spring Boot microservices."
   
   d) Data & Database:
      - Title: "Azure SQL Database Schema for Client Data and Transactions"
      - Description: "Design and implement database schema for client profiles, accounts, transactions, and audit logs. Include indexes for performance and foreign key constraints."
   
   e) External Integrations:
      - Title: "KYC/AML External Service Integration"
      - Description: "Integrate with third-party KYC/AML services for client identity verification and risk assessment. Implement async processing with Azure Functions."
   
   f) Cloud Infrastructure:
      - Title: "Azure API Management Gateway Configuration"
      - Description: "Set up Azure API Management as gateway for all client-facing APIs. Configure rate limiting, caching, and request/response transformation policies."
   
   g) Serverless Processing:
      - Title: "Azure Functions for Transaction Processing and Data Aggregation"
      - Description: "Create serverless functions for processing client transactions, calculating portfolio values, and aggregating data for reporting."
   
   h) DevOps & Monitoring:
      - Title: "Azure DevOps CI/CD Pipeline with Automated Deployment"
      - Description: "Set up complete CI/CD pipeline using Azure DevOps for automated build, test, and deployment to Azure App Service. Include Azure Monitoring for metrics and logs."

⚠️ IMPORTANT:
- Use ACTUAL project context from requirements
- Make titles SPECIFIC (not generic like "Create API")
- Include technical details in descriptions
- Call ado_wit_create_work_item for EACH work item (7-10 times)
- Use proper work item types: "Epic" for high-level, "Issue" for specific tasks

START CREATING NOW!
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
        tool_calls = result.get("tool_calls", [])
        
        # CHECK FOR TOOL CALL FAILURES
        failed_tool_calls = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool", "")
            tool_result = tool_call.get("result", {})
            
            if isinstance(tool_result, dict):
                if "text" in tool_result and "error" in tool_result["text"].lower():
                    logger.error(f"❌ MCP TOOL ERROR in work_items_agent: {tool_name}")
                    logger.error(f"   Error: {tool_result['text'][:200]}")
                    logger.error(f"   Args: {tool_call.get('args', {})}")
                    failed_tool_calls.append({
                        "tool": tool_name,
                        "error": tool_result["text"],
                        "args": tool_call.get("args", {})
                    })
        
        # Extract work item IDs from tool call results (more reliable than parsing output text)
        created_ids = []
        try:
            import os
            import re
            import json
            
            # FIRST: Extract IDs from successful tool call results
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool", "")
                # Match both with and without mcp_ prefix
                if "wit_create_work_item" in tool_name or tool_name == "ado_wit_create_work_item":
                    result = tool_call.get("result", {})
                    
                    # Method 1: Direct ID in result dict
                    if isinstance(result, dict) and "id" in result:
                        wi_id = result["id"]
                        if wi_id not in created_ids:
                            created_ids.append(wi_id)
                            logger.info(f"   ✅ Extracted work item ID {wi_id} from tool result")
                    
                    # Method 2: Parse ID from text field in result
                    elif isinstance(result, dict) and "text" in result:
                        text = result["text"]
                        # Look for "id": 1234 pattern in JSON-like text
                        id_match = re.search(r'"id":\s*(\d+)', text)
                        if id_match:
                            wi_id = int(id_match.group(1))
                            if wi_id not in created_ids:
                                created_ids.append(wi_id)
                                logger.info(f"   ✅ Parsed work item ID {wi_id} from tool result text")
            
            # FALLBACK: Try parsing URLs from output if no IDs found yet
            if not created_ids:
                logger.warning("⚠️  No IDs found in tool results, trying URL parsing from output...")
                id_pattern = r'/edit/(\d+)'
                matches = re.findall(id_pattern, output)
                created_ids = [int(id_str) for id_str in matches]
                if created_ids:
                    logger.info(f"   ✅ Parsed {len(created_ids)} work item IDs from URLs in output")
            
            if created_ids:
                logger.info(f"📋 Work Items Agent: Found {len(created_ids)} work item IDs")
                logger.info(f"📋 Work Items IDs: {created_ids}")
            else:
                logger.error("❌ CRITICAL: No work item IDs found!")
                logger.error(f"   Tool calls made: {tool_calls_made}")
                logger.error(f"   Failed tool calls: {len(failed_tool_calls)}")
                logger.error(f"   Total tool_calls inspected: {len(tool_calls)}")
                logger.error(f"   Output length: {len(output)}")
                logger.error(f"   Output preview: {output[:500]}")
                
        except Exception as parse_error:
            logger.error(f"❌ Exception parsing work item IDs: {parse_error}")
            import traceback
            logger.error("   Traceback:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    logger.error(f"   {line}")
        
        work_items = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "tool_calls_made": tool_calls_made,
            "created_ids": created_ids,  # Store IDs for test case creation
            "failed_tool_calls": failed_tool_calls,
        }
        
        requires_approval = decision_type == "request_approval"
        
        # Check if tools were actually called
        if tool_calls_made == 0:
            logger.error("❌ CRITICAL: Work items agent did not call any ADO tools!")
            logger.error("   This means no work items were created!")
        elif len(created_ids) == 0:
            logger.error("❌ CRITICAL: Tools were called but no work items were created!")
            logger.error(f"   Tool calls: {tool_calls_made}, Failed: {len(failed_tool_calls)}")
        
        # EXTENSIVE DEBUGGING FOR RETURN VALUE
        logger.info("="*80)
        logger.info("📋 WORK ITEMS AGENT - RETURNING STATE")
        logger.info("="*80)
        logger.info(f"created_ids: {created_ids}")
        logger.info(f"created_ids type: {type(created_ids)}")
        logger.info(f"created_ids length: {len(created_ids)}")
        logger.info(f"tool_calls_made: {tool_calls_made}")
        logger.info(f"failed_tool_calls: {len(failed_tool_calls)}") 
        logger.info(f"work_items dict to be returned: {work_items}")
        logger.info("="*80)
        
        return {
            "work_items": work_items,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "consecutive_failures": {},  # Reset failures on success
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
        logger.error(f"❌ EXCEPTION in work_items_agent_node: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        
        # Log full traceback
        import traceback
        logger.error("   Full traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                logger.error(f"   {line}")
        
        consecutive_failures = state.get("consecutive_failures", {})
        consecutive_failures["work_items"] = consecutive_failures.get("work_items", 0) + 1
        
        return {
            "errors": [f"Work items error: {str(e)}"],
            "consecutive_failures": consecutive_failures,
            "exception_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "work_items": {
                "created_ids": [],  # Ensure downstream nodes don't fail
                "description": f"Failed: {str(e)}",
            },
        }


async def _create_test_cases_directly(ado_client, work_items_details, project, test_plan_id, test_suite_id):
    """Direct fallback to create test cases when Deep Agent fails to call tools.
    
    This bypasses the autonomous Deep Agent and directly calls MCP tools.
    """
    logger.warning("🔧 DIRECT TEST CASE CREATION (Fallback Mode)")
    
    created_cases = []
    failed_tool_calls = []
    
    for idx, wi in enumerate(work_items_details, 1):
        wi_id = wi.get("id")
        wi_title = wi.get("title", "").strip()
        wi_desc = wi.get("description", "").strip()
        wi_type = wi.get("work_item_type", "Feature")
        wi_ac = wi.get("acceptance_criteria", "").strip()
        
        # Skip if this looks like it's already a test case
        if wi_type == "Test Case" or wi_title.lower().startswith("test:"):
            logger.warning(f"  [{idx}/{len(work_items_details)}] Skipping WI {wi_id} - appears to be a test case already")
            continue
        
        # If title is empty, skip
        if not wi_title:
            logger.error(f"  [{idx}/{len(work_items_details)}] Skipping WI {wi_id} - no title found")
            continue
        
        logger.info(f"  [{idx}/{len(work_items_details)}] Creating test for WI {wi_id}: {wi_title}")
        
        # Create CONTEXTUALIZED test case title based on work item type and content
        if wi_type == 'Epic':
            test_title = f"End-to-End Integration Test: {wi_title}"
        elif 'api' in wi_title.lower() or 'rest' in wi_title.lower():
            test_title = f"API Functional Test: {wi_title}"
        elif 'database' in wi_title.lower() or 'schema' in wi_title.lower():
            test_title = f"Data Validation Test: {wi_title}"
        elif 'auth' in wi_title.lower() or 'security' in wi_title.lower() or 'oauth' in wi_title.lower():
            test_title = f"Security & Authentication Test: {wi_title}"
        elif 'ui' in wi_title.lower() or 'dashboard' in wi_title.lower() or 'react' in wi_title.lower() or 'client' in wi_title.lower():
            test_title = f"UI/UX Functional Test: {wi_title}"
        elif 'integration' in wi_title.lower() or 'kyc' in wi_title.lower() or 'external' in wi_title.lower():
            test_title = f"Integration Test: {wi_title}"
        elif 'devops' in wi_title.lower() or 'pipeline' in wi_title.lower() or 'ci/cd' in wi_title.lower():
            test_title = f"DevOps & Deployment Test: {wi_title}"
        elif 'azure' in wi_title.lower() or 'cloud' in wi_title.lower():
            test_title = f"Cloud Infrastructure Test: {wi_title}"
        else:
            test_title = f"Functional Test: {wi_title}"
        
        # Limit title length
        if len(test_title) > 128:
            test_title = test_title[:125] + "..."
        
        # Build DETAILED test steps from work item details
        if wi_ac and len(wi_ac.strip()) > 10:
            steps = f"""1. Prerequisite Setup|Review requirement: {wi_title}. Set up test environment and test data. Verify all dependencies are available.
2. Test Execution - Acceptance Criteria|Execute test scenarios: {wi_ac[:200]}
3. Validation & Verification|Verify all acceptance criteria are met. Check for edge cases and error handling.
4. Cleanup & Documentation|Clean up test data. Document test results and any issues found."""
        elif wi_desc and len(wi_desc.strip()) > 10:
            steps = f"""1. Test Preparation|Review specification: {wi_title}. Understand requirements: {wi_desc[:200]}. Prepare test environment.
2. Execute Test Scenarios|Test primary functionality. Test error handling and edge cases. Verify integration points.
3. Results Validation|Confirm functionality matches requirements. Verify data integrity. Check performance and security.
4. Test Completion|Document test results. Report any defects found."""
        else:
            steps = f"""1. Test Setup|Review requirement: {wi_title}. Prepare test environment and data.
2. Test Execution|Execute primary test scenarios for {wi_type}. Test error handling. Verify expected behavior.
3. Validation|Verify all functionality works as expected. Check integration points.
4. Documentation|Document results and any issues."""
        
        try:
            # Create test case
            logger.info(f"      Calling testplan_create_test_case...")
            logger.info(f"      Title: {test_title}")
            result = await ado_client.call_tool('testplan_create_test_case', {
                'project': project,
                'title': test_title,
                'steps': steps,
                'priority': 2,
                'tests_work_item_id': wi_id
            }, timeout=60)
            
            # Check for error
            if isinstance(result, dict) and "error" in result:
                logger.error(f"      ❌ Failed to create test case: {result.get('text', 'Unknown error')}")
                failed_tool_calls.append({
                    "tool": "testplan_create_test_case",
                    "error": result.get("text"),
                    "args": {"wi_id": wi_id, "title": wi_title}
                })
                continue
            
            test_case_id = result.get("id")
            if not test_case_id:
                logger.error(f"      ❌ No test case ID returned: {result}")
                continue
            
            logger.info(f"      ✅ Created test case: {test_case_id}")
            
            # Add to suite
            logger.info(f"      Adding to suite {test_suite_id}...")
            result2 = await ado_client.call_tool('testplan_add_test_cases_to_suite', {
                'project': project,
                'planId': test_plan_id,
                'suiteId': test_suite_id,
                'testCaseIds': str(test_case_id)  # MUST be string!
            }, timeout=60)
            
            if isinstance(result2, dict) and "error" in result2:
                logger.error(f"      ❌ Failed to add to suite: {result2.get('text', 'Unknown error')}")
                failed_tool_calls.append({
                    "tool": "testplan_add_test_cases_to_suite",
                    "error": result2.get("text"),
                    "args": {"test_case_id": test_case_id}
                })
            else:
                logger.info(f"      ✅ Added to suite")
            
            created_cases.append({
                "test_case_id": test_case_id,
                "title": test_title,
                "plan_id": test_plan_id,
                "suite_id": test_suite_id,
                "result": "success",
                "work_item_id": wi_id
            })
            
        except Exception as e:
            logger.error(f"      ❌ Exception: {e}")
            failed_tool_calls.append({
                "tool": "direct_creation",
                "error": str(e),
                "args": {"wi_id": wi_id}
            })
    
    logger.info(f"🔧 Direct creation complete: {len(created_cases)} created, {len(failed_tool_calls)} failed")
    return created_cases, failed_tool_calls


# --- NEW: Test Plan Agent Node ---
async def test_plan_agent_node(state: DeepPipelineState) -> dict:
    """Test plan agent creates test cases using REST API + LLM.
    
    NEW APPROACH:
    - Queries ADO REST API for all work items
    - Uses LLM to generate contextualized test cases  
    - Creates via REST API (no Deep Agent)
    """
    import os
    from langchain_openai import ChatOpenAI
    
    logger.info("="*80)
    logger.info("🧪 TEST PLAN AGENT - Starting (REST API Mode)")
    logger.info("="*80)
    
    # Get ADO client
    ado_client = get_ado_client()
    if not ado_client:
        logger.error("❌ ADO client not initialized!")
        return {
            "test_plan_complete": True,
            "test_cases": [],
            "errors": ["ADO client not available"],
            "messages": [{"role": "qa_manager", "content": "❌ Cannot create test cases - ADO client not available"}]
        }
    
    # Get configuration from env
    test_plan_id = int(os.getenv("SDLC_TESTPLAN_ID", "369"))
    test_suite_id = int(os.getenv("SDLC_TESTSUITE_ID", "370"))
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    # STEP 1: Get work items from state (created by work_items agent) or query ADO
    logger.info("📋 Step 1: Getting work items...")
    work_items_details = []
    
    # FIRST: Try to use work item IDs from state (created by work_items_agent)
    work_items_data = state.get("work_items", {})
    created_ids = work_items_data.get("created_ids", [])
    
    if created_ids:
        logger.info(f"   ✅ Using {len(created_ids)} work item IDs from work_items_agent: {created_ids}")
        # Fetch details for each work item created by work_items_agent
        for wi_id in created_ids:
            try:
                wi_details = await ado_client.get_work_item(work_item_id=wi_id)
                fields = wi_details.get("fields", {})
                
                wi_type = fields.get("System.WorkItemType", "")
                # Skip test cases
                if wi_type == "Test Case":
                    continue
                
                wi_data = {
                    "id": wi_id,
                    "title": fields.get("System.Title", ""),
                    "description": fields.get("System.Description", ""),
                    "work_item_type": wi_type,
                    "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                }
                
                logger.info(f"   WI {wi_id}: {wi_type} - {wi_data['title'][:50]}")
                work_items_details.append(wi_data)
            except Exception as e:
                logger.error(f"   Failed to fetch WI {wi_id}: {e}")
    
    # FALLBACK: Query ADO for all work items if no created_ids
    if not work_items_details:
        logger.warning("   ⚠️ No created_ids from work_items_agent, falling back to WIQL query...")
        try:
            query_result = await ado_client.call_tool('work_query_by_wiql', {
                'project': project,
                'query': f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] <> 'Test Case'"
            }, timeout=30)
            
            if isinstance(query_result, dict) and "error" not in query_result:
                work_items = query_result.get("workItems", [])
                logger.info(f"   WIQL found {len(work_items)} work items")
                
                # Fetch details for each work item
                for wi in work_items[:10]:  # Limit to 10 most recent
                    wi_id = wi.get("id")
                    try:
                        wi_details = await ado_client.get_work_item(work_item_id=wi_id)
                        fields = wi_details.get("fields", {})
                        
                        wi_type = fields.get("System.WorkItemType", "")
                        # Skip test cases
                        if wi_type == "Test Case":
                            continue
                        
                        wi_data = {
                            "id": wi_id,
                            "title": fields.get("System.Title", ""),
                            "description": fields.get("System.Description", ""),
                            "work_item_type": wi_type,
                            "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                        }
                        
                        logger.info(f"   WI {wi_id}: {wi_type} - {wi_data['title'][:50]}")
                        work_items_details.append(wi_data)
                    except Exception as e:
                        logger.error(f"   Failed to fetch WI {wi_id}: {e}")
            
            # FALLBACK: If WIQL returns 0, try fetching recent work items by ID
            if not work_items_details:
                logger.warning("   WIQL returned 0 work items, trying fallback method...")
                # Try fetching last 30 work item IDs (assuming sequential IDs)
                for wi_id in range(1260, 1230, -1):  # Try IDs 1260 down to 1231
                    try:
                        wi_details = await ado_client.get_work_item(work_item_id=wi_id)
                        fields = wi_details.get("fields", {})
                        
                        wi_type = fields.get("System.WorkItemType", "")
                        # Skip test cases
                        if wi_type == "Test Case":
                            continue
                        
                        wi_data = {
                            "id": wi_id,
                            "title": fields.get("System.Title", ""),
                            "description": fields.get("System.Description", ""),
                            "work_item_type": wi_type,
                            "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                        }
                        
                        logger.info(f"   Fallback WI {wi_id}: {wi_type} - {wi_data['title'][:50]}")
                        work_items_details.append(wi_data)
                        
                        if len(work_items_details) >= 15:  # Increased limit to get more work items
                            break
                    except Exception:
                        # Work item doesn't exist, continue
                        pass
                
                logger.info(f"   Fallback method found {len(work_items_details)} work items")
        
        except Exception as e:
            logger.error(f"❌ Exception querying work items via WIQL: {e}")
    
    if not work_items_details:
        logger.warning("⚠️  No work items found to create test cases for")
        return {
            "test_plan_complete": True,
            "test_cases": [],
            "messages": [{"role": "qa_manager", "content": "⚠️ No work items found"}]
        }
    
    # STEP 2: Use LLM to generate contextualized test cases
    logger.info(f"🤖 Step 2: Using LLM to generate test cases for {len(work_items_details)} work items...")
    llm = ChatOpenAI(model="gpt-4", temperature=0.3)
    
    created_cases, failed_tool_calls = await _create_test_cases_with_llm(
        ado_client, llm, work_items_details, project, test_plan_id, test_suite_id
    )
    
    # STEP 3: Return results
    logger.info(f"✅ Test plan agent complete: {len(created_cases)} created, {len(failed_tool_calls)} failed")
    
    return {
        "test_cases": created_cases,
        "test_plan_complete": True,
        "failed_tool_calls": failed_tool_calls,
        "messages": [{
            "role": "qa_manager",
            "content": f"🧪 Created {len(created_cases)} test cases" + 
                      (f" ({len(failed_tool_calls)} failures)" if failed_tool_calls else ""),
        }],
        "decision_history": [{
            "agent": "test_plan",
            "decision": "complete",
            "confidence": "high",
            "test_cases_created": len(created_cases),
        }],
    }


async def _create_test_cases_with_llm(ado_client, llm, work_items_details, project, test_plan_id, test_suite_id):
    """Use LLM to generate contextualized test cases and create them via REST API."""
    import asyncio
    
    created_cases = []
    failed_tool_calls = []
    
    for idx, wi in enumerate(work_items_details, 1):
        wi_id = wi.get("id")
        wi_title = wi.get("title", "").strip()
        wi_desc = wi.get("description", "").strip()
        wi_type = wi.get("work_item_type", "Feature")
        wi_ac = wi.get("acceptance_criteria", "").strip()
        
        if not wi_title:
            logger.error(f"  [{idx}/{len(work_items_details)}] Skipping WI {wi_id} - no title")
            continue
        
        logger.info(f"  [{idx}/{len(work_items_details)}] Generating test for WI {wi_id}: {wi_title}")
        
        # Rate limiting: Add 2-second delay between LLM calls to avoid rate limits
        if idx > 1:
            logger.info(f"      ⏱️  Waiting 2 seconds to avoid rate limits...")
            await asyncio.sleep(2)
        
        # Use LLM to generate contextualized test case
        prompt = f"""You are a QA engineer creating a comprehensive test case for this work item:

WORK ITEM DETAILS:
Type: {wi_type}
Title: {wi_title}
Description: {wi_desc or 'Not provided'}
Acceptance Criteria: {wi_ac or 'Not provided'}

YOUR TASK:
Create a detailed, professional test case that validates this requirement.

TEST TITLE:
- Must be clear and specific (max 128 chars)
- Should indicate what is being tested
- Include the main feature/functionality name

TEST STEPS:
- Create 4-6 comprehensive test steps
- Each step should be actionable and specific
- Include setup, execution, and validation steps
- Cover positive scenarios and edge cases where applicable
- Format: "Step description|Expected result"
- Use '|' as delimiter between step and expected result
- Be specific about what to verify in expected results

RESPONSE FORMAT (follow exactly):
TEST_TITLE: [Clear, specific title reflecting the requirement]
TEST_STEPS:
1. [Specific setup/precondition step]|[What should be ready]
2. [First action to test the feature]|[Expected outcome with specific details]
3. [Second action or validation]|[Expected result with measurable criteria]
4. [Edge case or error scenario if applicable]|[Expected behavior]
5. [Verify integration points or side effects]|[Expected state]
6. [Cleanup or final validation]|[Expected final state]

Generate the test case now:"""

        try:
            # Call LLM with async
            response = await llm.ainvoke(prompt)
            llm_content = response.content
            
            # Parse LLM response
            test_title = ""
            test_steps = ""
            
            lines = llm_content.split("\n")
            in_steps = False
            steps_lines = []
            
            for line in lines:
                if line.startswith("TEST_TITLE:"):
                    test_title = line.replace("TEST_TITLE:", "").strip()
                elif line.startswith("TEST_STEPS:"):
                    in_steps = True
                elif in_steps and line.strip():
                    steps_lines.append(line.strip())
            
            test_steps = "\n".join(steps_lines)
            
            # Fallback if parsing failed
            if not test_title:
                test_title = f"Test: {wi_title}"
            if not test_steps:
                test_steps = f"1. Setup test environment|Environment is ready\n2. Execute test for {wi_title}|Feature works as expected\n3. Validate results|All criteria met\n4. Document findings|Results recorded"
            
            # Limit title length
            if len(test_title) > 128:
                test_title = test_title[:125] + "..."
            
            logger.info(f"      Title: {test_title}")
            
            # Create test case via REST API
            result = await ado_client.call_tool('testplan_create_test_case', {
                'project': project,
                'title': test_title,
                'steps': test_steps,
                'priority': 2,
                'tests_work_item_id': wi_id
            }, timeout=60)
            
            if isinstance(result, dict) and "error" in result:
                logger.error(f"      ❌ Failed: {result.get('text', 'Unknown error')}")
                failed_tool_calls.append({
                    "tool": "testplan_create_test_case",
                    "error": result.get("text"),
                    "args": {"wi_id": wi_id}
                })
                continue
            
            test_case_id = result.get("id")
            if not test_case_id:
                logger.error(f"      ❌ No test case ID returned")
                continue
            
            logger.info(f"      ✅ Created test case: {test_case_id}")
            
            # Add to suite
            result2 = await ado_client.call_tool('testplan_add_test_cases_to_suite', {
                'project': project,
                'planId': test_plan_id,
                'suiteId': test_suite_id,
                'testCaseIds': str(test_case_id)
            }, timeout=60)
            
            if isinstance(result2, dict) and "error" in result2:
                logger.error(f"      ❌ Failed to add to suite: {result2.get('text')}")
                failed_tool_calls.append({
                    "tool": "testplan_add_test_cases_to_suite",
                    "error": result2.get("text"),
                    "args": {"test_case_id": test_case_id}
                })
            else:
                logger.info(f"      ✅ Added to suite {test_suite_id}")
            
            created_cases.append({
                "test_case_id": test_case_id,
                "title": test_title,
                "plan_id": test_plan_id,
                "suite_id": test_suite_id,
                "work_item_id": wi_id
            })
            
        except Exception as e:
            logger.error(f"      ❌ Exception: {e}")
            failed_tool_calls.append({
                "tool": "llm_or_api",
                "error": str(e),
                "args": {"wi_id": wi_id}
            })
    
    return created_cases, failed_tool_calls


# --- Existing: Architecture Agent Node ---
async def architecture_agent_node(state: DeepPipelineState) -> dict:
    """Architecture agent designs system architecture using Northern Trust standards."""
    import asyncio
    import os
    from datetime import datetime
    
    agent = create_architecture_agent()
    
    requirements = state.get("requirements", {})
    work_items = state.get("work_items", {})
    test_cases = state.get("test_cases", [])
    
    # Read Northern Trust standards (async)
    standards_path = "docs/northern_trust_standards.md"
    standards_content = ""
    try:
        full_path = os.path.join(os.getcwd(), standards_path)
        
        # Use asyncio.to_thread for blocking file operations
        def read_standards():
            with open(full_path, 'r') as f:
                return f.read()
        
        standards_content = await asyncio.to_thread(read_standards)
        logger.info(f"📚 Loaded Northern Trust standards from {standards_path}")
    except Exception as e:
        logger.warning(f"Could not load Northern Trust standards: {e}")
        standards_content = "Northern Trust Technical Standards not available"
    
    task = f"""Design system architecture for:

Requirements:
{requirements.get('description', 'No requirements')}

Work Items:
{work_items.get('description', 'No work items') if work_items else 'Skipped'}

Test Cases Created:
{len(test_cases)} test cases created in ADO

=== NORTHERN TRUST TECHNICAL STANDARDS (MANDATORY) ===
{standards_content}

=== ARCHITECTURE REQUIREMENTS ===

You MUST design the architecture following Northern Trust standards:

1. **Cloud Platform**: Azure-native only (Azure App Service, Azure Functions, Azure SQL, etc.)
2. **Frontend**: React JS
3. **Backend**: Java-based microservices (Spring Boot recommended)
4. **Security**: Follow 2026 SSDLC requirements including:
   - Secure-by-Design and DevSecOps practices
   - End-to-end encryption (data in transit and at rest)
   - Strong IAM with MFA, RBAC
   - Compliance with PCI DSS, NIST Cybersecurity Framework, ISO 27001/27002
5. **Fraud Monitoring**: Risk-based, behavioral pattern analysis (Nacha 2026 compliance)
6. **Open Banking**: Secure APIs with OAuth 2.0 and OpenID Connect (CFPB Section 1033)

Generate:
1. High-level architecture diagram (use Mermaid MCP tools)
2. Component breakdown with Azure services
3. Technology stack aligned with Northern Trust standards
4. Security architecture (authentication, authorization, encryption)
5. Deployment architecture (CI/CD pipeline, environments)
6. Data flow diagrams

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
        tool_calls = result.get("tool_calls", [])
        
        # CHECK FOR TOOL FAILURES (especially Mermaid diagram generation)
        failed_tool_calls = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool", "")
            tool_result = tool_call.get("result", {})
            
            if isinstance(tool_result, dict):
                if "text" in tool_result and "error" in tool_result["text"].lower():
                    logger.error(f"❌ MCP TOOL ERROR in architecture_agent: {tool_name}")
                    logger.error(f"   Error: {tool_result['text'][:200]}")
                    logger.error(f"   Args: {tool_call.get('args', {})}")
                    failed_tool_calls.append({
                        "tool": tool_name,
                        "error": tool_result["text"],
                        "args": tool_call.get("args", {})
                    })
        
        if failed_tool_calls:
            logger.warning(f"⚠️  Architecture agent had {len(failed_tool_calls)} failed tool calls")
        
        # If max iterations reached, force completion and move to developer
        if iterations >= 5 or decision_type == "max_iterations":
            logger.info("🏗️ Architecture agent reached max 5 iterations, moving to developer")
            decision_type = "complete"
            confidence = "medium"
        
        # Save architecture documentation to docs/diagrams folder (async)
        docs_dir = "docs/diagrams"
        
        # Create directory using asyncio.to_thread
        await asyncio.to_thread(os.makedirs, docs_dir, exist_ok=True)
        
        project_name = state.get("project_name", "project")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save main architecture document (async)
        arch_doc_path = os.path.join(docs_dir, f"architecture_{project_name}_{timestamp}.md")
        
        def write_arch_doc():
            with open(arch_doc_path, 'w') as f:
                f.write(f"# Architecture Design - {project_name}\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Confidence:** {confidence}\n")
                f.write(f"**Iterations:** {iterations}\n")
                f.write(f"**Spawned Agents:** {spawned_count}\n\n")
                f.write("---\n\n")
                f.write(output)
        
        await asyncio.to_thread(write_arch_doc)
        logger.info(f"📄 Saved architecture document to {arch_doc_path}")
        
        # Extract and save Mermaid diagrams if present (async)
        saved_diagrams = []
        if "```mermaid" in output:
            import re
            mermaid_blocks = re.findall(r'```mermaid\n(.*?)```', output, re.DOTALL)
            for idx, diagram in enumerate(mermaid_blocks, 1):
                diagram_path = os.path.join(docs_dir, f"diagram_{project_name}_{timestamp}_{idx}.mmd")
                
                def write_diagram(path=diagram_path, content=diagram):
                    with open(path, 'w') as f:
                        f.write(content.strip())
                
                await asyncio.to_thread(write_diagram)
                saved_diagrams.append(diagram_path)
                logger.info(f"📊 Saved Mermaid diagram {idx} to {diagram_path}")
        
        architecture = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "spawned_agents": spawned_count,
            "saved_to": arch_doc_path,
            "diagrams": saved_diagrams,
            "failed_tool_calls": failed_tool_calls,
        }
        
        requires_approval = decision_type == "request_approval"
        
        return {
            "architecture": architecture,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "architect",
                "content": f"🏗️ Architecture designed and saved to {arch_doc_path}" + 
                          (f" ({len(failed_tool_calls)} tool calls failed)" if failed_tool_calls else ""),
                "details": output[:500] if output else "",
                "confidence": confidence,
                "spawned": spawned_count,
                "diagrams_saved": len(saved_diagrams),
            }],
            "decision_history": [{
                "agent": "architecture",
                "decision": decision_type,
                "confidence": confidence,
                "failed_tools": len(failed_tool_calls),
            }],
        }
    except Exception as e:
        logger.error(f"❌ EXCEPTION in architecture_agent_node: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        
        # Log full traceback
        import traceback
        logger.error("   Full traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                logger.error(f"   {line}")
        
        return {
            "errors": [f"Architecture error: {str(e)}"],
            "exception_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "architecture": {
                "description": f"Failed: {str(e)}",
                "confidence": "low",
                "saved_to": "",
            },
        }


async def developer_agent_node(state: DeepPipelineState) -> dict:
    """Developer generates code in ONE direct LLM call (no agent loop)."""
    import os
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    
    requirements = state.get("requirements", {})
    architecture = state.get("architecture", {})
    project_name = state.get("project_name", "new-project")
    
    # Extract full documentation
    arch_description = architecture.get('description', 'No architecture available') if architecture else 'No architecture available'
    req_description = requirements.get('description', 'No requirements available') if requirements else 'No requirements available'
    
    # Direct LLM call - NO AGENT LOOP, ONE SHOT
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    prompt = f"""Generate production-ready code for: {project_name}

ARCHITECTURE DOCUMENT (READ THIS CAREFULLY AND FOLLOW IT):
{arch_description}

REQUIREMENTS:
{req_description}

INSTRUCTIONS:
1. Analyze the architecture document above and identify ALL components mentioned (frontend, backend, database, API, services, etc.)
2. Generate a COMPLETE, COMPREHENSIVE implementation covering ALL architectural components
3. Include ALL necessary files for each component:
   - Frontend files (if architecture has frontend): HTML, CSS, JavaScript/React/Vue components
   - Backend files (if architecture has backend): API routes, controllers, services, middleware
   - Database files (if architecture has database): Models, schemas, migrations
   - Configuration files: .env.example, config files for each component
   - Deployment files: Dockerfiles, docker-compose.yml, kubernetes configs if mentioned
   - Documentation: README.md with setup for ALL components
   - Tests: Unit tests for backend, frontend tests if applicable
   - Package managers: requirements.txt, package.json, go.mod, etc. as needed
4. Generate 12-20+ files covering the FULL stack based on architecture complexity

CRITICAL OUTPUT FORMAT (follow exactly):
### FILE: path/to/file.ext
```language
# Actual working code here
```

### FILE: another/file.ext
```language
// More actual code
```

DO NOT generate placeholder text, Lorem Ipsum, or TODO comments. Generate REAL, WORKING code that implements EVERY part of the architecture document!"""
    
    try:
        logger.info(f"💻 Generating code with single LLM call (no agent loop)")
        
        messages = [
            SystemMessage(content="""You are a Senior Developer who generates REAL, WORKING code.

CRITICAL RULES:
1. Generate ACTUAL, FUNCTIONAL code - not examples, not placeholders
2. Follow the architecture document provided
3. Include proper imports, error handling, and working logic
4. Use the EXACT format: ### FILE: path \\n```language\\ncode\\n```
5. NO Lorem Ipsum, NO "example here", NO "TODO" comments - REAL CODE ONLY"""),
            HumanMessage(content=prompt)
        ]
        
        response = await llm.ainvoke(messages)
        output = response.content
        
        logger.info(f"✅ Code generated in single call ({len(output)} chars)")
        logger.info(f"📄 First 500 chars of generated output:")
        logger.info(f"{output[:500]}...")
        logger.info(f"📄 Last 500 chars of generated output:")
        logger.info(f"...{output[-500:]}")
        
        # Parse code artifacts from output
        confidence = "high"
        decision_type = "complete"
        iterations = 1
        spawned_count = 0
        tool_calls_made = 0
        
        logger.info(f"💻 Code generated successfully")
        
        # Use project_name from state (already set by project_name_prompt_node)
        repo_name = project_name.lower().replace(" ", "-").replace("_", "-")
        logger.info(f"📦 Using repository name from state: {repo_name}")
        
        # GitHub integration with direct tool calls for reliability
        github_results = {}
        owner = os.getenv("GITHUB_OWNER", os.getenv("GITHUB_USERNAME", ""))
        github_client = get_github_client()
        
        if owner and github_client:
            logger.info(f"🐙 Starting GitHub integration for: {owner}/{repo_name}")
            
            try:
                # Parse files from generated code
                import re
                
                # More robust regex - matches until we hit the NEXT "### FILE:" or end of string
                # This prevents issues with code containing triple backticks
                file_pattern = r'###\s*FILE:\s*([^\n]+)\s*\n```[^\n]*\n(.*?)(?=\n###\s*FILE:|\Z)'
                files = re.findall(file_pattern, output, re.DOTALL)
                
                # Clean up the captured content (remove trailing ```)
                cleaned_files = []
                for path, content in files:
                    # Remove trailing ``` if present
                    content = content.strip()
                    if content.endswith('```'):
                        content = content[:-3].strip()
                    cleaned_files.append((path, content))
                files = cleaned_files
                
                logger.info(f"📝 Parsed {len(files)} files from generated code")
                
                # Validate parsed files
                if files:
                    logger.info(f"📄 Files found:")
                    for i, (path, content) in enumerate(files[:3]):  # Log first 3
                        logger.info(f"  {i+1}. {path} ({len(content)} chars)")
                        if len(content) < 10:
                            logger.warning(f"    ⚠️ File {path} has very short content!")
                        logger.info(f"    Preview: {content[:100]}...")
                
                if len(files) == 0:
                    logger.warning("⚠️ No files found in generated code! Skipping GitHub push.")
                    github_results = {"error": "No files parsed from code output", "files_found": 0}
                else:
                    # Step 1: Create repository
                    try:
                        repo_result = await github_client.call_tool(
                            "create_repository",
                            {"name": repo_name, "owner": owner, "description": f"Generated by SDLC Pipeline - {project_name}", "private": False}
                        )
                        logger.info(f"✅ Repository created: {owner}/{repo_name}")
                    except Exception as e:
                        logger.warning(f"Repository may already exist: {e}")
                    
                    # Step 2: Create feature branch
                    branch_name = "feature/initial-implementation"
                    try:
                        await github_client.call_tool(
                            "create_branch",
                            {"owner": owner, "repo": repo_name, "branch": branch_name, "from_branch": "main"}
                        )
                        logger.info(f"✅ Branch created: {branch_name}")
                        target_branch = branch_name
                    except Exception as e:
                        logger.warning(f"Branch creation failed, using main: {e}")
                        target_branch = "main"
                    
                    # Step 3: Push files
                    pushed_files = []
                    failed_github_operations = []
                    
                    for file_path, file_content in files:
                        try:
                            file_path = file_path.strip()
                            file_content = file_content.strip()
                            
                            # Validate content is not empty or gibberish
                            if len(file_content) < 5:
                                logger.warning(f"  ⚠️ Skipping {file_path} - content too short ({len(file_content)} chars)")
                                continue
                            
                            # Check if content looks like actual code, not random gibberish
                            # Real code should have keywords, imports, or markdown headers
                            has_code_indicators = any([
                                'import ' in file_content,
                                'def ' in file_content,
                                'class ' in file_content,
                                'function ' in file_content,
                                '# ' in file_content,
                                '## ' in file_content,
                                '```' in file_content,
                                'const ' in file_content,
                                'var ' in file_content,
                                'let ' in file_content,
                                '{' in file_content and '}' in file_content,
                            ])
                            
                            if not has_code_indicators:
                                logger.warning(f"  ⚠️ Skipping {file_path} - content doesn't look like code/markdown:")
                                logger.warning(f"      Preview: {file_content[:200]}")
                                continue
                            
                            # GitHub MCP tool handles base64 encoding internally - send raw content
                            logger.info(f"  Pushing {file_path} ({len(file_content)} chars)")
                            logger.info(f"    Content preview: {file_content[:100]}...")
                            
                            result = await github_client.call_tool(
                                "create_or_update_file",
                                {
                                    "owner": owner,
                                    "repo": repo_name,
                                    "path": file_path,
                                    "content": file_content,  # Send raw content, MCP tool will encode
                                    "message": f"Add {file_path}",
                                    "branch": target_branch
                                }
                            )
                            
                            # CHECK FOR MCP ERROR RESPONSE
                            if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
                                logger.error(f"  ❌ GitHub MCP ERROR for {file_path}:")
                                logger.error(f"      {result['text']}")
                                failed_github_operations.append({
                                    "file": file_path,
                                    "operation": "create_or_update_file",
                                    "error": result["text"]
                                })
                            else:
                                pushed_files.append(file_path)
                                logger.info(f"  ✅ Pushed: {file_path}")
                                
                        except Exception as e:
                            logger.error(f"  ❌ Exception pushing {file_path}: {e}")
                            failed_github_operations.append({
                                "file": file_path,
                                "operation": "create_or_update_file",
                                "error": str(e)
                            })
                    
                    logger.info(f"✅ Pushed {len(pushed_files)}/{len(files)} files to GitHub")
                    if failed_github_operations:
                        logger.error(f"❌ {len(failed_github_operations)} GitHub operations failed")
                        for failure in failed_github_operations[:3]:  # Log first 3
                            logger.error(f"   - {failure['file']}: {failure['error'][:100]}")
                    
                    # Step 4: Create PR (only if using feature branch)
                    pr_url = ""
                    if target_branch != "main":
                        try:
                            pr_result = await github_client.call_tool(
                                "create_pull_request",
                                {
                                    "owner": owner,
                                    "repo": repo_name,
                                    "title": f"Initial Implementation: {project_name}",
                                    "body": f"## Generated by SDLC Pipeline\n\nThis PR contains the initial implementation.\n\nFiles: {', '.join(pushed_files)}",
                                    "head": target_branch,
                                    "base": "main"
                                }
                            )
                            pr_url = pr_result.get("html_url", "")
                            logger.info(f"✅ PR created: {pr_url}")
                        except Exception as e:
                            logger.error(f"PR creation failed: {e}")
                    
                    github_results = {
                        "repository_url": f"https://github.com/{owner}/{repo_name}",
                        "pull_request_url": pr_url,
                        "branch": target_branch,
                        "files_pushed": len(pushed_files),
                        "total_files": len(files),
                        "failed_operations": failed_github_operations,
                    }
                    
            except Exception as e:
                logger.error(f"GitHub integration failed: {e}")
                import traceback
                traceback.print_exc()
                github_results = {
                    "error": str(e),
                    "failed": True,
                }
        else:
            if not owner:
                logger.warning("GITHUB_OWNER not set, skipping GitHub integration")
                github_results["skipped"] = "GITHUB_OWNER not configured"
            else:
                logger.warning("GitHub client not initialized, skipping GitHub integration")
                github_results["skipped"] = "GitHub client not available"
        
        code_artifacts = {
            "description": output,
            "confidence": confidence,
            "iterations": iterations,
            "spawned_agents": spawned_count,
            "tool_calls": tool_calls_made,
            "github": github_results,
        }
        
        requires_approval = decision_type == "request_approval"
        
        pr_url = github_results.get("pull_request_url", "")
        repo_url = github_results.get("repository_url", "")
        
        return {
            "code_artifacts": code_artifacts,
            "github_results": github_results,
            "requires_approval": requires_approval,
            "approval_reason": output if requires_approval else None,
            "messages": [{
                "role": "developer",
                "content": f"💻 Code generated and pushed to GitHub. PR: {pr_url or 'not created'}",
                "details": output[:500] if output else "",
                "confidence": confidence,
                "spawned": spawned_count,
                "github": github_results,
            }],
            "decision_history": [{
                "agent": "development",
                "decision": decision_type,
                "confidence": confidence,
            }],
        }
    except Exception as e:
        logger.error(f"❌ EXCEPTION in developer_agent_node: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        
        # Log full traceback
        import traceback
        logger.error("   Full traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                logger.error(f"   {line}")
        
        return {
            "code_artifacts": {"error": str(e), "failed": True},  # CRITICAL: Set this so orchestrator knows we tried
            "errors": [f"Development error: {str(e)}"],
            "exception_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "messages": [{
                "role": "developer",
                "content": f"❌ Code generation failed: {str(e)}",
            }],
        }


async def project_name_prompt_node(state: DeepPipelineState) -> dict:
    """Prompt user for project name to use in GitHub operations."""
    user_query = state.get("user_query", "")
    suggested_name = user_query.lower().replace(" ", "-")[:50] if user_query else "new-project"
    
    logger.info(f"📝 Prompting user for GitHub repository name (suggested: {suggested_name})")
    
    response = interrupt({
        "type": "github_repository_name",
        "message": "GitHub Repository Name",
        "instructions": f"""Enter the GitHub repository name for this project.

Repository will be created at: rameshappat/<your-repo-name>

Suggested name: {suggested_name}

Enter repository name (or press Enter to use suggested):""",
        "suggested_name": suggested_name,
    })
    
    # Use user input or fall back to suggested name
    project_name = str(response).strip() if response and str(response).strip() else suggested_name
    # Sanitize project name for GitHub (lowercase, hyphens, no spaces)
    project_name = project_name.lower().replace(" ", "-").replace("_", "-")
    
    logger.info(f"✅ GitHub project name set to: {project_name}")
    
    return {
        "project_name": project_name,
        "messages": [{
            "role": "human",
            "content": f"📝 GitHub project: {project_name} | ADO project: testingmcp",
        }],
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
        "instructions": "Type 'approve' to continue or 'revise' to regenerate. Optionally, provide Test Plan Name, planId, suiteId (comma separated)",
    })

    # If approval is for test_plan, inject values into state
    test_plan_info = None
    if current_agent == "test_plan":
        # Parse user response for custom values, else use defaults
        # Accept: "approve" or "approve,MyPlan,123,456"
        parts = str(response).split(",")
        if len(parts) >= 4:
            plan_name = parts[1].strip()
            plan_id = int(parts[2].strip())
            suite_id = int(parts[3].strip())
        else:
            plan_name = "TestingMCPPlan"
            plan_id = 369
            suite_id = 370
        test_plan_info = {
            "description": f"Human provided/approved test plan info: {plan_name}, {plan_id}, {suite_id}",
            "confidence": "human",
            "iterations": 0,
            "tool_calls_made": 0,
            "plan_id": plan_id,
            "suite_id": suite_id,
            "plan_name": plan_name,
        }

    result = {
        "approval_response": response,
        "requires_approval": False,  # Clear the flag
        "messages": [{
            "role": "human",
            "content": f"User: {response}",
        }],
    }
    if test_plan_info:
        result["test_plan"] = test_plan_info
    return result


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
    """Route based on orchestrator decision."""
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
    builder.add_node("project_name_prompt", project_name_prompt_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("requirements", requirements_agent_node)
    builder.add_node("work_items", work_items_agent_node)
    builder.add_node("test_plan", test_plan_agent_node)
    builder.add_node("architecture", architecture_agent_node)
    builder.add_node("development", developer_agent_node)
    builder.add_node("approval", approval_node)
    builder.add_node("complete", complete_node)
    
    # Start -> Init -> Project Name Prompt -> Orchestrator
    builder.add_edge(START, "init")
    builder.add_edge("init", "project_name_prompt")
    builder.add_edge("project_name_prompt", "orchestrator")
    
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
        interrupt_before=["project_name_prompt", "approval"],  # Human-in-the-loop for project setup and approval checkpoints
    )


# Export the compiled graph for LangGraph Studio
graph = build_graph()
