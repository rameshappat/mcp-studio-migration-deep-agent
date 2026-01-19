"""Deep Agent Graph - Dynamic SDLC Pipeline with True Autonomous Agents.

This is a fully dynamic graph where:
1. Agents decide their own next steps (no fixed flow)
2. Agents spawn sub-agents as needed
3. Self-correction is automatic
4. Human approval is optional (confidence-based)
5. LLM has full autonomy over tools

Key differences from fixed graph:
- No predetermined node sequence
- Dynamic routing based on agent decisions
- Agents can skip stages or add new ones
- No hard-coded approval gates (confidence-based instead)
"""

import asyncio
import json
import logging
import os
from typing import Annotated, Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from typing_extensions import TypedDict

from .deep_agent import DeepAgent, ConfidenceLevel, SubAgentSpec

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# DYNAMIC STATE DEFINITION
# ============================================================================

class DynamicPipelineState(TypedDict, total=False):
    """State for dynamic deep agent pipeline."""
    # Input
    project_idea: str
    project_name: str
    
    # Conversation
    messages: Annotated[list, add_messages]
    
    # Agent execution tracking
    agent_history: list[dict[str, Any]]  # History of all agent executions
    current_agent: str  # Current active agent
    next_agent: str | None  # Next agent to run (dynamically determined)
    
    # Artifacts (dynamically created by agents)
    artifacts: dict[str, Any]  # All artifacts keyed by type
    
    # Configuration
    require_approval: bool  # Global approval setting
    confidence_threshold: str  # Minimum confidence for autonomy
    max_pipeline_iterations: int  # Prevent infinite loops
    
    # Execution state
    pipeline_iteration: int
    completed: bool
    requires_human_input: bool
    human_feedback: str | None


# ============================================================================
# MCP CLIENT INITIALIZATION (same as before)
# ============================================================================

_ado_client = None
_github_client = None
_mermaid_client = None


def get_ado_client():
    """Get or create ADO MCP client."""
    global _ado_client
    if _ado_client is None:
        org = os.getenv("AZURE_DEVOPS_ORGANIZATION")
        project = os.getenv("AZURE_DEVOPS_PROJECT")
        if org and project:
            try:
                from src.mcp_client.ado_client import AzureDevOpsMCPClient
                _ado_client = AzureDevOpsMCPClient(organization=org, project=project)
                logger.info(f"ADO client initialized for {org}/{project}")
            except Exception as e:
                logger.warning(f"Could not initialize ADO client: {e}")
    return _ado_client


def get_github_client():
    """Get or create GitHub MCP client."""
    global _github_client
    if _github_client is None:
        mcp_url = os.getenv("GITHUB_MCP_URL")
        token = os.getenv("GITHUB_TOKEN")
        if mcp_url and token:
            try:
                from src.mcp_client.github_client import GitHubMCPClient
                _github_client = GitHubMCPClient(mcp_url=mcp_url, github_token=token)
                logger.info(f"GitHub client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize GitHub client: {e}")
    return _github_client


def get_mermaid_client():
    """Get or create Mermaid MCP client."""
    global _mermaid_client
    if _mermaid_client is None:
        try:
            from src.mcp_client.mermaid_client import MermaidMCPClient
            _mermaid_client = MermaidMCPClient()
            logger.info("Mermaid client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Mermaid client: {e}")
    return _mermaid_client


# ============================================================================
# UNIVERSAL TOOLS - Available to all agents
# ============================================================================

@tool
def save_artifact(artifact_type: str, artifact_data: dict) -> str:
    """Save an artifact to the pipeline state.
    
    Args:
        artifact_type: Type of artifact (requirements, architecture, code, etc.)
        artifact_data: The artifact data as a dictionary
    """
    return json.dumps({"status": "saved", "type": artifact_type})


@tool
async def ado_create_work_item(work_item_type: str, title: str, description: str = "", parent_id: int = None) -> str:
    """Create a work item in Azure DevOps. Types: Epic, Issue, Task, Bug."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        fields = {
            "System.Title": title,
            "System.Description": description or "",
            "System.WorkItemType": work_item_type,
        }
        
        if parent_id:
            result = await client.create_work_item(
                work_item_type=work_item_type,
                fields=fields,
                parent_id=parent_id,
            )
        else:
            result = await client.create_work_item(
                work_item_type=work_item_type,
                fields=fields,
            )
        
        return json.dumps({"status": "created", "id": result.get("id"), "url": result.get("url", "")})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def ado_list_iterations() -> str:
    """List all iteration paths in Azure DevOps project."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        result = await client.list_iterations()
        paths = [it.get("path", "") for it in result]
        return json.dumps({"iterations": paths[:10]})  # Limit to 10
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def github_create_repo(name: str, description: str = "", private: bool = False) -> str:
    """Create a new GitHub repository."""
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        result = await client.call_tool("create_repository", {
            "name": name,
            "description": description,
            "private": private,
            "autoInit": True,
        })
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        if "already exists" in str(e).lower():
            return json.dumps({"status": "exists"})
        return json.dumps({"error": str(e)})


@tool
async def github_push_code(owner: str, repo: str, files: list[dict], branch: str = "main") -> str:
    """Push code files to GitHub repository.
    
    Args:
        owner: GitHub username/organization
        repo: Repository name
        files: List of {path: str, content: str} dicts
        branch: Branch name (will be created if doesn't exist)
    """
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        # Create branch if needed
        if branch != "main":
            await client.call_tool("create_branch", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "from_branch": "main",
            })
        
        # Push files
        result = await client.call_tool("push_files", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "files": files,
            "message": f"feat: Add generated code",
        })
        
        return json.dumps({"status": "success", "files": len(files)})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def render_diagram(mermaid_code: str, output_path: str) -> str:
    """Render a Mermaid diagram to PNG file."""
    client = get_mermaid_client()
    if not client:
        return json.dumps({"error": "Mermaid client not configured"})
    
    try:
        result = await client.render_diagram(mermaid_code, output_path)
        return json.dumps({"status": "rendered", "path": output_path})
    except Exception as e:
        return json.dumps({"error": str(e)})


# All tools available to agents
ALL_TOOLS = [
    save_artifact,
    ado_create_work_item,
    ado_list_iterations,
    github_create_repo,
    github_push_code,
    render_diagram,
]


# ============================================================================
# ORCHESTRATOR AGENT - Manages the pipeline flow
# ============================================================================

ORCHESTRATOR_OBJECTIVE = """You are the Orchestrator Agent managing an SDLC pipeline.

Your responsibilities:
1. Analyze the project requirements
2. Decide which specialized agents to invoke and in what order
3. Monitor progress and decide when to move to the next phase
4. Coordinate handoffs between agents
5. Determine when the pipeline is complete

You can dynamically choose the pipeline flow based on the project needs.
Standard flow: Requirements → Work Items → Architecture → Development → Deployment
But you can skip stages, add custom stages, or reorder as needed.

When making decisions:
- Consider project complexity
- Check if previous stages are complete
- Decide if parallel work is possible
- Determine if human review is needed (based on confidence)

Use the 'save_artifact' tool to record decisions and handoffs.
"""


# ============================================================================
# SPECIALIZED AGENTS - Each handles a specific concern
# ============================================================================

REQUIREMENTS_AGENT_OBJECTIVE = """You are a Product Manager specialized in requirements gathering.

Your task is to:
1. Analyze the project idea
2. Define functional and non-functional requirements
3. Identify user personas and use cases
4. Specify constraints and assumptions
5. Prioritize requirements

Generate a comprehensive requirements document.
Use save_artifact(artifact_type='requirements', artifact_data={...}) to store results.
"""

WORK_ITEMS_AGENT_OBJECTIVE = """You are a Business Analyst specialized in work decomposition.

Your task is to:
1. Review requirements
2. Create Epics for major feature areas
3. Break epics into User Stories
4. Add acceptance criteria to each story
5. Estimate story points
6. Optionally push to Azure DevOps using ado_create_work_item()

Use save_artifact(artifact_type='work_items', artifact_data={...}) to store results.
"""

ARCHITECTURE_AGENT_OBJECTIVE = """You are a Software Architect.

Your task is to:
1. Design system architecture based on requirements
2. Define components, modules, and their interactions
3. Choose technology stack
4. Create architecture diagrams (C4, sequence diagrams)
5. Document design decisions

Use render_diagram() to create visual diagrams.
Use save_artifact(artifact_type='architecture', artifact_data={...}) to store results.
"""

DEVELOPER_AGENT_OBJECTIVE = """You are a Senior Software Developer.

Your task is to:
1. Implement the architecture
2. Generate production-quality code
3. Include error handling, logging, and tests
4. Create configuration files
5. Optionally push to GitHub using github_create_repo() and github_push_code()

Use save_artifact(artifact_type='code', artifact_data={...}) to store results.
"""


# ============================================================================
# DYNAMIC GRAPH NODES
# ============================================================================

def create_deep_agent(
    role: str,
    objective: str,
    state: DynamicPipelineState,
) -> DeepAgent:
    """Create a deep agent with configuration from state."""
    
    confidence_str = state.get("confidence_threshold", "medium")
    confidence_level = ConfidenceLevel(confidence_str)
    
    return DeepAgent(
        role=role,
        objective=objective,
        tools=ALL_TOOLS,
        model_name=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
        temperature=0.7,
        provider=os.getenv("SDLC_LLM_PROVIDER_DEFAULT", "openai"),
        max_iterations=10,
        min_confidence_for_autonomy=confidence_level,
        enable_self_correction=True,
        enable_agent_spawning=True,
    )


async def orchestrator_node(state: DynamicPipelineState) -> dict:
    """Orchestrator decides the next step dynamically."""
    
    logger.info("[Orchestrator] Analyzing pipeline state and deciding next step")
    
    # Create orchestrator agent
    agent = create_deep_agent(
        role="Orchestrator",
        objective=ORCHESTRATOR_OBJECTIVE,
        state=state,
    )
    
    # Build context with current artifacts
    context = {
        "project_idea": state.get("project_idea", ""),
        "project_name": state.get("project_name", ""),
        "artifacts": state.get("artifacts", {}),
        "agent_history": state.get("agent_history", []),
        "iteration": state.get("pipeline_iteration", 0),
    }
    
    task = """Analyze the current pipeline state and decide the next step.

Consider what has been completed and what remains.
Decide which specialized agent should run next, or if pipeline is complete.

Respond with JSON:
{
    "next_agent": "requirements|work_items|architecture|developer|none",
    "reasoning": "Why this agent should run next",
    "is_complete": true/false,
    "requires_approval": true/false
}
"""
    
    result = await agent.execute(task, context)
    
    # Parse orchestrator decision
    output = result.get("output", "")
    try:
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0]
        decision = json.loads(output.strip())
    except:
        # Default: complete if we don't understand
        decision = {"next_agent": "none", "is_complete": True, "requires_approval": False}
    
    # Record this execution
    agent_history = state.get("agent_history", [])
    agent_history.append({
        "agent": "orchestrator",
        "iteration": state.get("pipeline_iteration", 0),
        "decision": decision,
        "result": result,
    })
    
    next_agent = decision.get("next_agent", "none")
    is_complete = decision.get("is_complete", False)
    requires_approval = decision.get("requires_approval", False)
    
    logger.info(f"[Orchestrator] Decision: next_agent={next_agent}, complete={is_complete}")
    
    return {
        "current_agent": "orchestrator",
        "next_agent": next_agent if not is_complete else None,
        "completed": is_complete,
        "requires_human_input": requires_approval and state.get("require_approval", False),
        "agent_history": agent_history,
        "messages": [AIMessage(content=f"Orchestrator: {decision.get('reasoning', '')}")],
    }


async def requirements_agent_node(state: DynamicPipelineState) -> dict:
    """Requirements agent generates requirements."""
    
    logger.info("[Requirements] Generating project requirements")
    
    agent = create_deep_agent(
        role="Requirements Agent",
        objective=REQUIREMENTS_AGENT_OBJECTIVE,
        state=state,
    )
    
    context = {
        "project_idea": state.get("project_idea", ""),
        "project_name": state.get("project_name", ""),
    }
    
    result = await agent.execute(
        f"Generate comprehensive requirements for: {context['project_idea']}",
        context,
    )
    
    # Extract artifacts from result
    artifacts = state.get("artifacts", {})
    # Agent should have called save_artifact, but we'll try to parse from output too
    output = result.get("output", "")
    if "requirements" in output.lower():
        # Agent generated requirements, store them
        artifacts["requirements"] = {
            "output": output,
            "result": result,
        }
    
    agent_history = state.get("agent_history", [])
    agent_history.append({
        "agent": "requirements",
        "iteration": state.get("pipeline_iteration", 0),
        "result": result,
    })
    
    return {
        "current_agent": "requirements",
        "artifacts": artifacts,
        "agent_history": agent_history,
        "messages": [AIMessage(content=f"✅ Requirements generated")],
    }


async def work_items_agent_node(state: DynamicPipelineState) -> dict:
    """Work items agent creates epics and stories."""
    
    logger.info("[Work Items] Creating work items")
    
    agent = create_deep_agent(
        role="Work Items Agent",
        objective=WORK_ITEMS_AGENT_OBJECTIVE,
        state=state,
    )
    
    context = {
        "project_name": state.get("project_name", ""),
        "artifacts": state.get("artifacts", {}),
    }
    
    result = await agent.execute(
        "Create epics and user stories from requirements. Optionally push to Azure DevOps.",
        context,
    )
    
    artifacts = state.get("artifacts", {})
    artifacts["work_items"] = {
        "output": result.get("output", ""),
        "result": result,
    }
    
    agent_history = state.get("agent_history", [])
    agent_history.append({
        "agent": "work_items",
        "iteration": state.get("pipeline_iteration", 0),
        "result": result,
    })
    
    return {
        "current_agent": "work_items",
        "artifacts": artifacts,
        "agent_history": agent_history,
        "messages": [AIMessage(content=f"✅ Work items created")],
    }


async def architecture_agent_node(state: DynamicPipelineState) -> dict:
    """Architecture agent designs the system."""
    
    logger.info("[Architecture] Designing system architecture")
    
    agent = create_deep_agent(
        role="Architecture Agent",
        objective=ARCHITECTURE_AGENT_OBJECTIVE,
        state=state,
    )
    
    context = {
        "project_name": state.get("project_name", ""),
        "artifacts": state.get("artifacts", {}),
    }
    
    result = await agent.execute(
        "Design the system architecture. Create diagrams.",
        context,
    )
    
    artifacts = state.get("artifacts", {})
    artifacts["architecture"] = {
        "output": result.get("output", ""),
        "result": result,
    }
    
    agent_history = state.get("agent_history", [])
    agent_history.append({
        "agent": "architecture",
        "iteration": state.get("pipeline_iteration", 0),
        "result": result,
    })
    
    return {
        "current_agent": "architecture",
        "artifacts": artifacts,
        "agent_history": agent_history,
        "messages": [AIMessage(content=f"✅ Architecture designed")],
    }


async def developer_agent_node(state: DynamicPipelineState) -> dict:
    """Developer agent implements the code."""
    
    logger.info("[Developer] Implementing code")
    
    agent = create_deep_agent(
        role="Developer Agent",
        objective=DEVELOPER_AGENT_OBJECTIVE,
        state=state,
    )
    
    context = {
        "project_name": state.get("project_name", ""),
        "artifacts": state.get("artifacts", {}),
    }
    
    result = await agent.execute(
        "Implement the architecture. Generate code and optionally push to GitHub.",
        context,
    )
    
    artifacts = state.get("artifacts", {})
    artifacts["code"] = {
        "output": result.get("output", ""),
        "result": result,
    }
    
    agent_history = state.get("agent_history", [])
    agent_history.append({
        "agent": "developer",
        "iteration": state.get("pipeline_iteration", 0),
        "result": result,
    })
    
    return {
        "current_agent": "developer",
        "artifacts": artifacts,
        "agent_history": agent_history,
        "messages": [AIMessage(content=f"✅ Code implemented")],
    }


async def human_input_node(state: DynamicPipelineState) -> dict:
    """Request human input when confidence is low."""
    
    current_agent = state.get("current_agent", "unknown")
    
    response = interrupt({
        "type": "human_input_required",
        "agent": current_agent,
        "message": f"Agent {current_agent} requires your input to proceed.",
        "instructions": "Provide feedback or type 'continue' to proceed.",
    })
    
    return {
        "human_feedback": response,
        "requires_human_input": False,
        "messages": [HumanMessage(content=f"Human: {response}")],
    }


async def completed_node(state: DynamicPipelineState) -> dict:
    """Pipeline completed."""
    logger.info("[Pipeline] Completed successfully!")
    
    return {
        "completed": True,
        "messages": [AIMessage(content="🎉 SDLC Pipeline completed!")],
    }


# ============================================================================
# DYNAMIC ROUTING LOGIC
# ============================================================================

def route_pipeline(state: DynamicPipelineState) -> str:
    """Dynamically route to next node based on state."""
    
    # Check for completion
    if state.get("completed", False):
        return "completed"
    
    # Check for human input requirement
    if state.get("requires_human_input", False):
        return "human_input"
    
    # Check iteration limit
    iteration = state.get("pipeline_iteration", 0)
    max_iterations = state.get("max_pipeline_iterations", 20)
    if iteration >= max_iterations:
        logger.warning(f"Max pipeline iterations ({max_iterations}) reached")
        return "completed"
    
    # Route to next agent (decided by orchestrator)
    next_agent = state.get("next_agent")
    
    if next_agent == "requirements":
        return "requirements"
    elif next_agent == "work_items":
        return "work_items"
    elif next_agent == "architecture":
        return "architecture"
    elif next_agent == "developer":
        return "developer"
    elif next_agent == "none" or not next_agent:
        return "completed"
    else:
        # Unknown agent, go back to orchestrator
        return "orchestrator"


def route_after_agent(state: DynamicPipelineState) -> str:
    """After any specialized agent runs, go back to orchestrator."""
    
    # Increment pipeline iteration
    return "orchestrator"


# ============================================================================
# BUILD DYNAMIC GRAPH
# ============================================================================

def build_dynamic_graph():
    """Build the dynamic deep agent graph."""
    
    builder = StateGraph(DynamicPipelineState)
    
    # Initialize node
    async def initialize(state: DynamicPipelineState) -> dict:
        project_idea = state.get("project_idea", "")
        project_name = state.get("project_name", "new-project")
        
        return {
            "project_idea": project_idea,
            "project_name": project_name,
            "messages": [AIMessage(content=f"🚀 Starting dynamic pipeline for: {project_name}")],
            "artifacts": {},
            "agent_history": [],
            "pipeline_iteration": 0,
            "completed": False,
            "requires_human_input": False,
            "confidence_threshold": state.get("confidence_threshold", "medium"),
            "require_approval": state.get("require_approval", False),
            "max_pipeline_iterations": state.get("max_pipeline_iterations", 20),
        }
    
    # Increment iteration after each orchestrator decision
    async def increment_iteration(state: DynamicPipelineState) -> dict:
        return {
            "pipeline_iteration": state.get("pipeline_iteration", 0) + 1,
        }
    
    # Add nodes
    builder.add_node("initialize", initialize)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("increment", increment_iteration)
    builder.add_node("requirements", requirements_agent_node)
    builder.add_node("work_items", work_items_agent_node)
    builder.add_node("architecture", architecture_agent_node)
    builder.add_node("developer", developer_agent_node)
    builder.add_node("human_input", human_input_node)
    builder.add_node("completed", completed_node)
    
    # Add edges
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "orchestrator")
    
    # Dynamic routing from orchestrator
    builder.add_conditional_edges(
        "orchestrator",
        route_pipeline,
        {
            "requirements": "requirements",
            "work_items": "work_items",
            "architecture": "architecture",
            "developer": "developer",
            "human_input": "human_input",
            "completed": "completed",
        }
    )
    
    # All specialized agents go back to orchestrator (with iteration increment)
    builder.add_edge("requirements", "increment")
    builder.add_edge("work_items", "increment")
    builder.add_edge("architecture", "increment")
    builder.add_edge("developer", "increment")
    builder.add_edge("increment", "orchestrator")
    
    # Human input loops back to orchestrator
    builder.add_edge("human_input", "orchestrator")
    
    # Completed goes to END
    builder.add_edge("completed", END)
    
    # Compile with optional interrupts (only for human input)
    return builder.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_input"] if os.getenv("ENABLE_HUMAN_APPROVAL", "false").lower() == "true" else [],
    )


# Export graph
dynamic_graph = build_dynamic_graph()
