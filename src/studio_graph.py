"""LangGraph Studio wrapper for SDLC Pipeline.

This module wraps the existing SDLCPipelineOrchestrator agents in a LangGraph StateGraph
to enable visualization and interaction in LangSmith Studio.

COMPLETE PIPELINE STAGES:
1. initialize
2. requirements → requirements_approval
3. work_items → work_items_approval
4. ado_push_confirm → ado_push
5. test_plan_confirm → test_plan_input → test_plan
6. architecture → architecture_approval
7. mermaid_render_confirm → mermaid_render
8. development → development_approval
9. github_push_confirm → github_push_input → github_push
10. completed / failed
"""

import os
import logging
from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

# Import existing agents and pipeline components
from src.agents import (
    AgentContext,
    AgentRole,
    ApprovalStatus,
    ProductManagerAgent,
    BusinessAnalystAgent,
    ArchitectAgent,
    DeveloperAgent,
)
from src.agents.base_agent import AgentMessage

logger = logging.getLogger(__name__)


def reducer(current: list, new: list | None) -> list:
    """Reducer for message lists - appends new messages."""
    if new is None:
        return current
    return current + new


class PipelineGraphState(TypedDict, total=False):
    """State for the SDLC Pipeline LangGraph."""
    
    # Input
    project_idea: str
    project_name: str
    
    # Pipeline state
    current_stage: str
    messages: Annotated[list[dict], reducer]
    
    # Agent outputs
    requirements: dict | None
    epics: list[dict] | None
    user_stories: list[dict] | None
    architecture: dict | None
    code_artifacts: dict | None
    
    # ADO integration
    ado_results: dict | None
    ado_test_plan: dict | None
    
    # GitHub integration
    github_results: dict | None
    github_pr: dict | None
    
    # Mermaid rendering
    mermaid_results: dict | None
    
    # User inputs (collected via interrupts)
    test_plan_inputs: dict | None
    github_inputs: dict | None
    
    # Approval tracking
    pending_approval: dict | None
    approval_response: str | None
    confirmation_response: str | None
    revision_feedback: str | None
    
    # Error handling
    errors: list[str]


# ============================================================================
# CLIENT AND AGENT INITIALIZATION
# ============================================================================

_ado_client = None
_github_client = None
_agents = None


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
                _ado_client = None
    return _ado_client


def get_github_client():
    """Lazily initialize GitHub MCP client."""
    global _github_client
    if _github_client is None:
        mcp_url = os.getenv("GITHUB_MCP_URL")
        token = os.getenv("GITHUB_TOKEN")
        
        print(f"[DEBUG] GitHub init: MCP_URL={mcp_url[:30] if mcp_url else 'None'}..., TOKEN={'set' if token else 'None'}")
        
        if mcp_url and token:
            try:
                from src.mcp_client.github_client import GitHubMCPClient
                _github_client = GitHubMCPClient(
                    mcp_url=mcp_url,
                    github_token=token,
                )
                print(f"[DEBUG] ✅ GitHub client created successfully")
                logger.info(f"GitHub client initialized for {mcp_url}")
            except Exception as e:
                print(f"[DEBUG] ❌ GitHub client creation failed: {e}")
                logger.warning(f"Could not initialize GitHub client: {e}")
                import traceback
                traceback.print_exc()
                _github_client = None
        else:
            if not mcp_url:
                print("[DEBUG] ❌ GITHUB_MCP_URL not set")
                logger.warning("GITHUB_MCP_URL not set")
            if not token:
                print("[DEBUG] ❌ GITHUB_TOKEN not set")
                logger.warning("GITHUB_TOKEN not set")
    return _github_client


def get_agents():
    """Lazily initialize agents with proper clients."""
    global _agents
    
    # Check if we need to reinitialize due to client changes
    if _agents is not None:
        # If GitHub client is now available but wasn't before, reinitialize
        github_client = get_github_client()
        if github_client and _agents["developer"]._github_client is None:
            print("[DEBUG] Reinitializing agents because GitHub client is now available")
            _agents = None
    
    if _agents is None:
        ado_client = get_ado_client()
        github_client = get_github_client()
        
        print(f"[DEBUG] Initializing agents: ADO={ado_client is not None}, GitHub={github_client is not None}")
        
        _agents = {
            "product_manager": ProductManagerAgent(),
            "business_analyst": BusinessAnalystAgent(ado_client=ado_client),
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(github_client=github_client),
        }
    return _agents


# ============================================================================
# NODE FUNCTIONS - INITIALIZATION
# ============================================================================

async def initialize_node(state: PipelineGraphState) -> dict:
    """Initialize the pipeline."""
    project_name = state.get("project_name", "new-project")
    return {
        "current_stage": "requirements",
        "messages": [{
            "role": "system",
            "content": f"🚀 Starting SDLC Pipeline for: {project_name}",
            "stage": "initialization"
        }],
        "errors": [],
    }


# ============================================================================
# NODE FUNCTIONS - REQUIREMENTS
# ============================================================================

async def requirements_node(state: PipelineGraphState) -> dict:
    """Generate requirements using Product Manager agent."""
    agents = get_agents()
    pm = agents["product_manager"]
    
    context = AgentContext()
    context.project_name = state.get("project_name", "new-project")
    context.project_description = state.get("project_idea", "")
    
    try:
        message = await pm.generate_requirements(context, domain=state.get("project_idea", ""))
        requirements = message.artifacts.get("requirements", {})
        
        return {
            "current_stage": "requirements_approval",
            "requirements": requirements,
            "messages": [{
                "role": "assistant",
                "content": f"📋 Product Manager generated requirements",
                "stage": "requirements",
                "agent": "product_manager",
                "details": message.content[:500] if message.content else ""
            }],
            "pending_approval": {
                "stage": "requirements",
                "content": message.content,
                "artifacts": message.artifacts,
            },
        }
    except Exception as e:
        return {
            "current_stage": "failed",
            "errors": [f"Requirements generation failed: {str(e)}"],
            "messages": [{"role": "error", "content": f"Error: {str(e)}", "stage": "requirements"}]
        }


async def requirements_approval_node(state: PipelineGraphState) -> dict:
    """Human-in-the-loop approval for requirements."""
    pending = state.get("pending_approval", {})
    
    response = interrupt({
        "type": "approval",
        "stage": "requirements",
        "message": "📋 Please review the generated requirements.",
        "instructions": "Type 'approve' to continue, 'revise' to regenerate, or 'reject' to stop.",
        "content_preview": (pending.get("content", "")[:2000] + "...") if len(pending.get("content", "")) > 2000 else pending.get("content", ""),
    })
    
    return {
        "approval_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "requirements_approval"}]
    }


def route_after_requirements_approval(state: PipelineGraphState) -> str:
    response = str(state.get("approval_response", "")).lower().strip()
    if response in ("approve", "approved", "yes", "y", "ok"):
        return "work_items"
    elif response in ("revise", "revision", "edit", "redo"):
        return "requirements"
    else:
        return "failed"


# ============================================================================
# NODE FUNCTIONS - WORK ITEMS
# ============================================================================

async def work_items_node(state: PipelineGraphState) -> dict:
    """Generate epics and user stories using Business Analyst agent."""
    agents = get_agents()
    ba = agents["business_analyst"]
    
    context = AgentContext()
    context.project_name = state.get("project_name", "new-project")
    context.requirements = state.get("requirements", {})
    
    try:
        req_message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Requirements generated",
            artifacts={"requirements": state.get("requirements", {})}
        )
        
        message = await ba.create_work_items(context, req_message)
        work_items = message.artifacts.get("work_items", {})
        epics = work_items.get("epics", [])
        stories = work_items.get("stories", [])
        
        return {
            "current_stage": "work_items_approval",
            "epics": epics,
            "user_stories": stories,
            "messages": [{
                "role": "assistant",
                "content": f"📝 Business Analyst created {len(epics)} epics and {len(stories)} user stories",
                "stage": "work_items",
                "agent": "business_analyst"
            }],
            "pending_approval": {
                "stage": "work_items",
                "content": message.content[:2000] if message.content else "",
                "epics_count": len(epics),
                "stories_count": len(stories),
            },
        }
    except Exception as e:
        return {
            "current_stage": "failed",
            "errors": [f"Work items generation failed: {str(e)}"],
            "messages": [{"role": "error", "content": f"Error: {str(e)}", "stage": "work_items"}]
        }


async def work_items_approval_node(state: PipelineGraphState) -> dict:
    """Human-in-the-loop approval for work items."""
    pending = state.get("pending_approval", {})
    
    response = interrupt({
        "type": "approval",
        "stage": "work_items",
        "message": f"📝 Please review {pending.get('epics_count', 0)} epics and {pending.get('stories_count', 0)} user stories.",
        "instructions": "Type 'approve' to continue, 'revise' to regenerate, or 'reject' to stop.",
    })
    
    return {
        "approval_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "work_items_approval"}]
    }


def route_after_work_items_approval(state: PipelineGraphState) -> str:
    response = str(state.get("approval_response", "")).lower().strip()
    if response in ("approve", "approved", "yes", "y", "ok"):
        return "ado_push_confirm"
    elif response in ("revise", "revision", "edit", "redo"):
        return "work_items"
    else:
        return "failed"


# ============================================================================
# NODE FUNCTIONS - ADO PUSH
# ============================================================================

async def ado_push_confirm_node(state: PipelineGraphState) -> dict:
    """Confirm whether to push work items to Azure DevOps."""
    ado_client = get_ado_client()
    
    if not ado_client:
        return {
            "confirmation_response": "skip",
            "messages": [{"role": "system", "content": "⚠️ ADO client not configured - skipping", "stage": "ado_push_confirm"}]
        }
    
    response = interrupt({
        "type": "confirmation",
        "stage": "ado_push",
        "message": "☁️ Push work items to Azure DevOps?",
        "instructions": "Type 'yes' to push to ADO, or 'skip' to continue without pushing.",
    })
    
    return {
        "confirmation_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "ado_push_confirm"}]
    }


def route_after_ado_push_confirm(state: PipelineGraphState) -> str:
    response = str(state.get("confirmation_response", "")).lower().strip()
    if response in ("yes", "y", "push", "ok", "approve"):
        return "ado_push"
    else:
        return "test_plan_confirm"


async def ado_push_node(state: PipelineGraphState) -> dict:
    """Push work items to Azure DevOps."""
    agents = get_agents()
    ba = agents["business_analyst"]
    
    context = AgentContext()
    context.project_name = state.get("project_name", "new-project")
    context.epics = state.get("epics", [])
    context.stories = state.get("user_stories", [])
    
    try:
        result = await ba.push_to_azure_devops(context)
        
        if "error" in result:
            return {
                "current_stage": "test_plan_confirm",
                "ado_results": result,
                "messages": [{"role": "warning", "content": f"⚠️ ADO push failed: {result['error']}", "stage": "ado_push"}]
            }
        
        epics_created = len(result.get("epics", []))
        stories_created = len(result.get("stories", []))
        
        return {
            "current_stage": "test_plan_confirm",
            "ado_results": result,
            "messages": [{"role": "assistant", "content": f"✅ Pushed to ADO: {epics_created} epics, {stories_created} stories", "stage": "ado_push"}]
        }
    except Exception as e:
        return {
            "current_stage": "test_plan_confirm",
            "ado_results": {"error": str(e)},
            "messages": [{"role": "warning", "content": f"⚠️ ADO push error: {str(e)}", "stage": "ado_push"}]
        }


# ============================================================================
# NODE FUNCTIONS - TEST PLAN (Multi-step input)
# ============================================================================

def _normalize_ado_path(path: str) -> str:
    """Normalize ADO iteration path."""
    p = (path or "").strip()
    if not p:
        return p
    p = p.replace("/", "\\")
    while "\\\\" in p:
        p = p.replace("\\\\", "\\")
    if not p.startswith("\\"):
        p = "\\" + p
    return p


def _flatten_iteration_paths(nodes: object) -> list[str]:
    """Extract iteration paths from ADO response."""
    paths: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, dict):
            p = n.get("path")
            if isinstance(p, str) and p.strip():
                paths.append(p.strip())
            children = n.get("children")
            if isinstance(children, list):
                for c in children:
                    walk(c)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(nodes)
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def _story_to_test_steps(story: dict) -> str:
    """Convert a BA story into Azure Test Plans step format."""

    def _clean(s: str) -> str:
        return (s or "").replace("|", "/").strip()

    ac = story.get("acceptance_criteria") or []
    if not isinstance(ac, list):
        ac = [str(ac)]

    lines: list[str] = []
    idx = 1
    for item in ac:
        item_s = _clean(str(item))
        if not item_s:
            continue
        lines.append(f"{idx}. {item_s}|{item_s}")
        idx += 1

    if not lines:
        title = _clean(str(story.get("title") or "the feature"))
        lines.append(f"1. Verify {title} works end-to-end|{title} behaves as specified")

    return "\n".join(lines)


def _extract_int_id(value: object, keys: tuple) -> int | None:
    """Extract integer ID from various response formats."""
    import json
    import re

    def _from_text(text: str) -> int | None:
        s = (text or "").strip()
        if not s:
            return None
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                parsed = json.loads(s)
                return _extract_int_id(parsed, keys)
            except Exception:
                pass
        for key in keys:
            m = re.search(rf'"{re.escape(key)}"\s*:\s*(\d+)', s)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None
        for key in keys:
            m = re.search(rf'\b{re.escape(key)}\b\s*[:=]\s*(\d+)', s)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None
        return None

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _from_text(value)
    if isinstance(value, list):
        for item in value:
            found = _extract_int_id(item, keys)
            if found:
                return found
        return None
    if isinstance(value, dict):
        for k in keys:
            v = value.get(k)
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.isdigit():
                return int(v)
        text = value.get("text")
        if isinstance(text, str):
            found = _from_text(text)
            if found:
                return found
        for v in value.values():
            found = _extract_int_id(v, keys)
            if found:
                return found
    return None


def _get_response_str(response: Any) -> str:
    """Safely convert interrupt response to string."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        # If it's a dict, try to get a meaningful value
        return str(response.get("value", response.get("text", ""))).strip()
    return str(response).strip()


async def test_plan_confirm_node(state: PipelineGraphState) -> dict:
    """Confirm whether to create an Azure DevOps Test Plan and fetch iterations."""
    ado_client = get_ado_client()
    
    if not ado_client:
        return {
            "confirmation_response": "skip",
            "messages": [{"role": "system", "content": "⚠️ ADO client not configured - skipping Test Plan", "stage": "test_plan_confirm"}]
        }
    
    # Fetch available iterations to show to user
    iteration_paths: list[str] = []
    try:
        iters = await ado_client.call_tool(
            "work_list_iterations",
            {"project": ado_client.project, "depth": 10},
        )
        iteration_paths = [_normalize_ado_path(p) for p in _flatten_iteration_paths(iters)]
    except Exception as e:
        logger.warning(f"Could not fetch iterations: {e}")
    
    iterations_display = "\n".join(f"  • {p}" for p in iteration_paths[:15]) if iteration_paths else "  (Could not retrieve iterations)"
    
    response = interrupt({
        "type": "confirmation",
        "stage": "test_plan",
        "message": "🧪 Create an Azure DevOps Test Plan?",
        "instructions": """Options:
  • Type 'new' to create a NEW Test Plan
  • Type 'existing' to use an EXISTING Plan ID and Suite ID
  • Type 'skip' to continue without a Test Plan""",
        "available_iterations": iterations_display,
        "note": f"Found {len(iteration_paths)} iteration path(s) in project '{ado_client.project}'"
    })
    
    response_str = _get_response_str(response).lower()
    
    return {
        "confirmation_response": response_str,
        "test_plan_inputs": {"available_iterations": iteration_paths},
        "messages": [{"role": "human", "content": f"User: {response_str}", "stage": "test_plan_confirm"}]
    }


def route_after_test_plan_confirm(state: PipelineGraphState) -> str:
    response = _get_response_str(state.get("confirmation_response", "")).lower()
    if response in ("new", "yes", "y", "create"):
        return "test_plan_input_name"
    elif response in ("existing", "exist", "use"):
        return "test_plan_input_existing"
    else:
        return "architecture"


async def test_plan_input_name_node(state: PipelineGraphState) -> dict:
    """Input: Test Plan Name."""
    project_name = state.get("project_name", "new-project")
    default_name = f"{project_name} - Test Plan"
    
    response = interrupt({
        "type": "input",
        "stage": "test_plan_input_name",
        "message": "🧪 Step 1/3: Enter Test Plan Name",
        "instructions": f"Enter a name for the Test Plan, or press Enter for default.",
        "default": default_name,
    })
    
    response_str = _get_response_str(response)
    plan_name = response_str if response_str else default_name
    
    existing_inputs = state.get("test_plan_inputs", {})
    existing_inputs["plan_name"] = plan_name
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Plan Name: {plan_name}", "stage": "test_plan_input_name"}]
    }


async def test_plan_input_iteration_node(state: PipelineGraphState) -> dict:
    """Input: Iteration Path (with list of available iterations)."""
    existing_inputs = state.get("test_plan_inputs", {})
    available_iterations = existing_inputs.get("available_iterations", [])
    
    # Number the iterations for easy selection
    iterations_list = []
    for i, path in enumerate(available_iterations[:20], 1):
        iterations_list.append(f"  {i}. {path}")
    iterations_display = "\n".join(iterations_list) if iterations_list else "  (none found)"
    
    response = interrupt({
        "type": "input",
        "stage": "test_plan_input_iteration",
        "message": "🧪 Step 2/3: Select Iteration Path",
        "instructions": f"""Available Iterations:
{iterations_display}

Enter the iteration number (e.g., '1') or paste the full path.
Type 'skip' to cancel Test Plan creation.""",
    })
    
    response_str = _get_response_str(response)
    
    if response_str.lower() in ("skip", "cancel", ""):
        existing_inputs["iteration"] = None
        return {
            "test_plan_inputs": existing_inputs,
            "messages": [{"role": "human", "content": "User cancelled - no iteration selected", "stage": "test_plan_input_iteration"}]
        }
    
    # Check if user entered a number
    if response_str.isdigit():
        idx = int(response_str) - 1
        if 0 <= idx < len(available_iterations):
            iteration = available_iterations[idx]
        else:
            iteration = _normalize_ado_path(response_str)
    else:
        iteration = _normalize_ado_path(response_str)
    
    existing_inputs["iteration"] = iteration
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Iteration: {iteration}", "stage": "test_plan_input_iteration"}]
    }


async def test_plan_input_description_node(state: PipelineGraphState) -> dict:
    """Input: Description (optional)."""
    response = interrupt({
        "type": "input",
        "stage": "test_plan_input_description",
        "message": "🧪 Step 3/3: Enter Description (optional)",
        "instructions": "Enter a description for the Test Plan, or press Enter to skip.",
    })
    
    response_str = _get_response_str(response)
    
    existing_inputs = state.get("test_plan_inputs", {})
    existing_inputs["description"] = response_str if response_str.lower() not in ("skip", "") else ""
    existing_inputs["use_existing"] = False
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Description: {existing_inputs['description'] or '(none)'}", "stage": "test_plan_input_description"}]
    }


async def test_plan_input_existing_node(state: PipelineGraphState) -> dict:
    """Input: Existing Plan ID and Suite ID."""
    existing_inputs = state.get("test_plan_inputs", {})
    available_iterations = existing_inputs.get("available_iterations", [])
    
    # First get Plan ID
    plan_response = interrupt({
        "type": "input",
        "stage": "test_plan_input_existing_plan",
        "message": "🧪 Enter Existing Test Plan ID",
        "instructions": "Enter the numeric Plan ID from Azure DevOps (e.g., '123').\nType 'skip' to cancel.",
    })
    
    plan_str = _get_response_str(plan_response)
    
    if plan_str.lower() in ("skip", "cancel", ""):
        return {
            "test_plan_inputs": None,
            "messages": [{"role": "human", "content": "User cancelled", "stage": "test_plan_input_existing"}]
        }
    
    try:
        plan_id = int(plan_str)
    except ValueError:
        return {
            "test_plan_inputs": {"error": f"Invalid Plan ID: {plan_str}"},
            "messages": [{"role": "warning", "content": f"Invalid Plan ID: {plan_str}", "stage": "test_plan_input_existing"}]
        }
    
    existing_inputs["plan_id"] = plan_id
    existing_inputs["use_existing"] = True
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Plan ID: {plan_id}", "stage": "test_plan_input_existing"}]
    }


async def test_plan_input_suite_node(state: PipelineGraphState) -> dict:
    """Input: Existing Suite ID."""
    existing_inputs = state.get("test_plan_inputs", {})
    
    suite_response = interrupt({
        "type": "input",
        "stage": "test_plan_input_suite",
        "message": "🧪 Enter Existing Test Suite ID",
        "instructions": "Enter the numeric Suite ID from Azure DevOps (e.g., '456').\nType 'skip' to cancel.",
    })
    
    suite_str = _get_response_str(suite_response)
    
    if suite_str.lower() in ("skip", "cancel", ""):
        return {
            "test_plan_inputs": None,
            "messages": [{"role": "human", "content": "User cancelled", "stage": "test_plan_input_suite"}]
        }
    
    try:
        suite_id = int(suite_str)
    except ValueError:
        return {
            "test_plan_inputs": {"error": f"Invalid Suite ID: {suite_str}"},
            "messages": [{"role": "warning", "content": f"Invalid Suite ID: {suite_str}", "stage": "test_plan_input_suite"}]
        }
    
    existing_inputs["suite_id"] = suite_id
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Suite ID: {suite_id}", "stage": "test_plan_input_suite"}]
    }


async def test_plan_input_iteration_existing_node(state: PipelineGraphState) -> dict:
    """Input: Iteration Path for existing plan (needed for test case creation)."""
    existing_inputs = state.get("test_plan_inputs", {})
    available_iterations = existing_inputs.get("available_iterations", [])
    
    iterations_list = []
    for i, path in enumerate(available_iterations[:20], 1):
        iterations_list.append(f"  {i}. {path}")
    iterations_display = "\n".join(iterations_list) if iterations_list else "  (none found)"
    
    response = interrupt({
        "type": "input",
        "stage": "test_plan_input_iteration_existing",
        "message": "🧪 Select Iteration Path for Test Cases",
        "instructions": f"""Available Iterations:
{iterations_display}

Enter the iteration number or paste the full path.""",
    })
    
    response_str = _get_response_str(response)
    
    if response_str.isdigit():
        idx = int(response_str) - 1
        if 0 <= idx < len(available_iterations):
            iteration = available_iterations[idx]
        else:
            iteration = _normalize_ado_path(response_str)
    else:
        iteration = _normalize_ado_path(response_str)
    
    existing_inputs["iteration"] = iteration
    
    return {
        "test_plan_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Iteration: {iteration}", "stage": "test_plan_input_iteration_existing"}]
    }


def route_after_test_plan_input_iteration(state: PipelineGraphState) -> str:
    """Route after iteration input."""
    inputs = state.get("test_plan_inputs", {})
    if inputs and inputs.get("iteration"):
        return "test_plan_input_description"
    else:
        return "architecture"


def route_after_test_plan_input_description(state: PipelineGraphState) -> str:
    """Route after description input."""
    inputs = state.get("test_plan_inputs", {})
    if inputs and inputs.get("iteration"):
        return "test_plan"
    else:
        return "architecture"


def route_after_test_plan_input_existing(state: PipelineGraphState) -> str:
    """Route after existing plan ID input."""
    inputs = state.get("test_plan_inputs", {})
    if inputs and inputs.get("plan_id"):
        return "test_plan_input_suite"
    else:
        return "architecture"


def route_after_test_plan_input_suite(state: PipelineGraphState) -> str:
    """Route after suite ID input."""
    inputs = state.get("test_plan_inputs", {})
    if inputs and inputs.get("suite_id"):
        return "test_plan_input_iteration_existing"
    else:
        return "architecture"


def route_after_test_plan_input_iteration_existing(state: PipelineGraphState) -> str:
    """Route after iteration input for existing plan."""
    inputs = state.get("test_plan_inputs", {})
    if inputs and inputs.get("iteration"):
        return "test_plan"
    else:
        return "architecture"


async def test_plan_node(state: PipelineGraphState) -> dict:
    """Create Azure DevOps Test Plan with Suite and Test Cases."""
    ado_client = get_ado_client()
    inputs = state.get("test_plan_inputs", {})
    
    if not ado_client or not inputs:
        return {
            "current_stage": "architecture",
            "messages": [{"role": "system", "content": "⚠️ Skipping Test Plan creation", "stage": "test_plan"}]
        }
    
    use_existing = inputs.get("use_existing", False)
    iteration = inputs.get("iteration", "")
    available_iterations = inputs.get("available_iterations", [])
    stories = list(state.get("user_stories", []) or [])
    
    if not iteration:
        return {
            "current_stage": "architecture",
            "ado_test_plan": {"error": "No iteration path provided"},
            "messages": [{"role": "warning", "content": "⚠️ No iteration path provided - skipping Test Plan", "stage": "test_plan"}]
        }
    
    try:
        if use_existing:
            # Use existing Plan ID and Suite ID
            plan_id = inputs.get("plan_id")
            suite_id = inputs.get("suite_id")
            
            if not plan_id or not suite_id:
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"error": "Plan ID and Suite ID required"},
                    "messages": [{"role": "warning", "content": "⚠️ Plan ID and Suite ID are required", "stage": "test_plan"}]
                }
            
            logger.info(f"Using existing Plan ID: {plan_id}, Suite ID: {suite_id}")
            
        else:
            # Create NEW Test Plan
            plan_name = inputs.get("plan_name", f"{state.get('project_name', 'project')} - Test Plan")
            description = inputs.get("description", "")
            
            # Validate iteration path
            if available_iterations and iteration not in available_iterations:
                examples = "\n".join(f"  • {p}" for p in available_iterations[:10])
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"error": f"Invalid iteration path: {iteration}"},
                    "messages": [{
                        "role": "warning",
                        "content": f"⚠️ Iteration path '{iteration}' not found.\n\nValid paths:\n{examples}",
                        "stage": "test_plan"
                    }]
                }
            
            # Step 1: Create Test Plan
            result = await ado_client.create_test_plan(
                name=plan_name,
                iteration=iteration,
                description=description or None,
            )
            
            if result is None:
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"error": "Test Plan creation returned null"},
                    "messages": [{"role": "warning", "content": "⚠️ Test Plan creation failed", "stage": "test_plan"}]
                }
            
            # Check for auth errors
            if isinstance(result, dict) and isinstance(result.get("text"), str):
                text_lower = result["text"].lower()
                if "not authorized" in text_lower or "unauthorized" in text_lower:
                    return {
                        "current_stage": "architecture",
                        "ado_test_plan": {"error": result["text"]},
                        "messages": [{"role": "warning", "content": f"⚠️ Auth error: {result['text']}", "stage": "test_plan"}]
                    }
            
            logger.info(f"Test Plan created: {result}")
            
            # Extract plan ID
            plan_id = _extract_int_id(result, keys=("id", "planId"))
            
            if not plan_id:
                # Fallback: list plans and find by name
                try:
                    plans = await ado_client.call_tool(
                        "testplan_list_test_plans",
                        {"project": ado_client.project, "filterActivePlans": True, "includePlanDetails": True},
                    )
                    if isinstance(plans, list):
                        for p in plans:
                            if isinstance(p, dict):
                                if p.get("name") == plan_name and isinstance(p.get("id"), int):
                                    plan_id = p["id"]
                                    break
                except Exception as e:
                    logger.warning(f"Could not look up plan id: {e}")
            
            if not plan_id:
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"plan_created": True, "error": "Could not determine Plan ID"},
                    "messages": [{"role": "warning", "content": "✅ Plan created but could not get Plan ID", "stage": "test_plan"}]
                }
            
            # Step 2: Create Test Suite
            suite_name = f"{state.get('project_name', 'project')} - MVP Regression"
            suite = await ado_client.create_test_suite(
                plan_id=plan_id,
                parent_suite_id=plan_id,
                name=suite_name,
            )
            
            suite_id = _extract_int_id(suite, keys=("id", "suiteId"))
            if not suite_id:
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"plan_id": plan_id, "error": "Could not create suite"},
                    "messages": [{"role": "warning", "content": f"✅ Plan ID: {plan_id} but suite creation failed", "stage": "test_plan"}]
                }
            
            logger.info(f"Suite created: ID={suite_id}")
        
        # Step 3: Create Test Cases from stories
        created_case_ids: list[int] = []
        
        for story in stories:
            title = str(story.get("title") or story.get("id") or "Story")
            story_id = str(story.get("id") or "")
            tc_title = f"{story_id}: {title}" if story_id else title
            steps = _story_to_test_steps(story)
            priority = int(story.get("priority") or 2)
            
            try:
                tc = await ado_client.create_test_case(
                    title=tc_title,
                    steps=steps,
                    priority=priority,
                    iteration_path=iteration,
                )
                tc_id = _extract_int_id(tc, keys=("id", "workItemId"))
                if tc_id:
                    created_case_ids.append(tc_id)
                    logger.info(f"Created test case: {tc_title} (ID: {tc_id})")
            except Exception as e:
                logger.warning(f"Failed to create test case for {story_id}: {e}")
        
        # Step 4: Add Test Cases to Suite
        if created_case_ids:
            try:
                await ado_client.add_test_cases_to_suite(
                    plan_id=plan_id,
                    suite_id=suite_id,
                    test_case_ids=created_case_ids,
                )
                logger.info(f"Added {len(created_case_ids)} test cases to suite {suite_id}")
                
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {
                        "plan_id": plan_id,
                        "suite_id": suite_id,
                        "test_case_ids": created_case_ids,
                        "test_cases_created": len(created_case_ids),
                    },
                    "messages": [{
                        "role": "assistant",
                        "content": f"✅ Test Plan complete!\n  • Plan ID: {plan_id}\n  • Suite ID: {suite_id}\n  • Test Cases: {len(created_case_ids)} added",
                        "stage": "test_plan"
                    }]
                }
            except Exception as e:
                return {
                    "current_stage": "architecture",
                    "ado_test_plan": {"plan_id": plan_id, "suite_id": suite_id, "test_case_ids": created_case_ids, "error": str(e)},
                    "messages": [{"role": "warning", "content": f"✅ Created {len(created_case_ids)} test cases but failed to add to suite: {e}", "stage": "test_plan"}]
                }
        else:
            return {
                "current_stage": "architecture",
                "ado_test_plan": {"plan_id": plan_id, "suite_id": suite_id, "test_cases_created": 0},
                "messages": [{"role": "assistant", "content": f"✅ Plan ID: {plan_id}, Suite ID: {suite_id} (no test cases - no stories found)", "stage": "test_plan"}]
            }
        
    except Exception as e:
        return {
            "current_stage": "architecture",
            "ado_test_plan": {"error": str(e)},
            "messages": [{"role": "warning", "content": f"⚠️ Test Plan failed: {str(e)}", "stage": "test_plan"}]
        }


# ============================================================================
# NODE FUNCTIONS - ARCHITECTURE
# ============================================================================

async def architecture_node(state: PipelineGraphState) -> dict:
    """Generate architecture using Architect agent."""
    agents = get_agents()
    architect = agents["architect"]
    
    context = AgentContext()
    context.project_name = state.get("project_name", "new-project")
    context.project_description = state.get("project_idea", "")
    context.requirements = state.get("requirements", {})
    context.epics = state.get("epics", [])
    context.stories = state.get("user_stories", [])
    
    try:
        ba_message = AgentMessage(
            from_agent=AgentRole.BUSINESS_ANALYST,
            to_agent=AgentRole.ARCHITECT,
            content="Work items generated",
            artifacts={"work_items": {"epics": state.get("epics", []), "stories": state.get("user_stories", [])}}
        )
        
        message = await architect.create_architecture(context, ba_message)
        architecture = message.artifacts.get("architecture", {})
        
        return {
            "current_stage": "architecture_approval",
            "architecture": architecture,
            "messages": [{
                "role": "assistant",
                "content": f"🏗️ Architect created design with {len(architecture.get('components', []))} components",
                "stage": "architecture",
                "agent": "architect"
            }],
            "pending_approval": {
                "stage": "architecture",
                "content": message.content[:2000] if message.content else "",
            },
        }
    except Exception as e:
        return {
            "current_stage": "failed",
            "errors": [f"Architecture design failed: {str(e)}"],
            "messages": [{"role": "error", "content": f"Error: {str(e)}", "stage": "architecture"}]
        }


async def architecture_approval_node(state: PipelineGraphState) -> dict:
    """Human-in-the-loop approval for architecture."""
    response = interrupt({
        "type": "approval",
        "stage": "architecture",
        "message": "🏗️ Please review the system architecture design.",
        "instructions": "Type 'approve' to continue, 'revise' to regenerate, or 'reject' to stop.",
    })
    
    return {
        "approval_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "architecture_approval"}]
    }


def route_after_architecture_approval(state: PipelineGraphState) -> str:
    response = str(state.get("approval_response", "")).lower().strip()
    if response in ("approve", "approved", "yes", "y", "ok"):
        return "mermaid_render_confirm"
    elif response in ("revise", "revision", "edit", "redo"):
        return "architecture"
    else:
        return "failed"


# ============================================================================
# NODE FUNCTIONS - MERMAID RENDER
# ============================================================================

async def mermaid_render_confirm_node(state: PipelineGraphState) -> dict:
    """Confirm whether to render Mermaid diagrams."""
    response = interrupt({
        "type": "confirmation",
        "stage": "mermaid_render",
        "message": "📊 Render Mermaid diagrams to image files?",
        "instructions": "Type 'yes' to render diagrams via Mermaid MCP, or 'skip' to continue.",
        "note": "Requires local Mermaid MCP server running."
    })
    
    return {
        "confirmation_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "mermaid_render_confirm"}]
    }


def route_after_mermaid_render_confirm(state: PipelineGraphState) -> str:
    response = str(state.get("confirmation_response", "")).lower().strip()
    if response in ("yes", "y", "render", "ok"):
        return "mermaid_render"
    else:
        return "development"


async def mermaid_render_node(state: PipelineGraphState) -> dict:
    """Use LLM agent to render Mermaid diagrams - handles errors dynamically."""
    import asyncio
    
    architecture = state.get("architecture", {})
    
    # Look for diagrams in multiple possible locations
    diagrams = {}
    
    if isinstance(architecture, dict):
        diagrams = architecture.get("diagrams", {})
    
    if not diagrams and isinstance(architecture, dict):
        for key in ["c4_context", "c4_container", "c4_component", "sequence_main", "sequence_diagram"]:
            if key in architecture and isinstance(architecture[key], str):
                diagrams[key] = architecture[key]
    
    if not diagrams and isinstance(architecture, dict):
        for key, value in architecture.items():
            if isinstance(value, str) and ("graph " in value or "sequenceDiagram" in value or "flowchart" in value or "C4" in value):
                diagrams[key] = value
    
    logger.info(f"Found {len(diagrams)} diagrams to render: {list(diagrams.keys())}")
    
    if not diagrams:
        return {
            "current_stage": "development",
            "mermaid_results": {"skipped": True, "reason": "No Mermaid diagrams found"},
            "messages": [{"role": "system", "content": "⚠️ No Mermaid diagrams found in architecture", "stage": "mermaid_render"}]
        }
    
    output_dir = os.getenv("SDLC_MERMAID_OUTPUT_DIR", "docs/diagrams")
    
    # Run all blocking operations in a thread pool to avoid event loop issues
    async def render_all_diagrams():
        import concurrent.futures
        
        def render_single(key: str, mermaid_code: str) -> dict:
            """Render a single diagram - runs in thread."""
            try:
                import os
                os.makedirs(output_dir, exist_ok=True)
                
                out_path = os.path.join(output_dir, f"{key}.png")
                
                # Try to use MermaidMCPClient
                try:
                    from src.mcp_client import MermaidMCPClient
                    client = MermaidMCPClient()
                    
                    # Run sync version or create event loop for async
                    import asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(client.render_mermaid_to_file(mermaid_code, out_path))
                        loop.close()
                        return {"key": key, "status": "success", "path": out_path}
                    except Exception as e:
                        return {"key": key, "status": "error", "error": str(e)}
                except ImportError:
                    return {"key": key, "status": "error", "error": "MermaidMCPClient not available"}
                    
            except Exception as e:
                return {"key": key, "status": "error", "error": str(e)}
        
        # Use thread pool to run all renders in parallel
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(render_single, key, value): key 
                for key, value in diagrams.items() 
                if isinstance(value, str)
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    key = futures[future]
                    results.append({"key": key, "status": "error", "error": str(e)})
        
        return results
    
    try:
        # Run in thread to avoid blocking detection
        results = await asyncio.to_thread(lambda: asyncio.run(render_all_diagrams()))
        
        successes = [r for r in results if r.get("status") == "success"]
        errors = [r for r in results if r.get("status") == "error"]
        
        msg = f"📊 Rendered {len(successes)}/{len(diagrams)} diagram(s) to {output_dir}/"
        if errors:
            error_msgs = [f"{e['key']}: {e.get('error', 'Unknown')[:30]}" for e in errors[:3]]
            msg += f"\n  Errors: {'; '.join(error_msgs)}"
        
        return {
            "current_stage": "development",
            "mermaid_results": {"rendered": len(successes), "total": len(diagrams), "output_dir": output_dir, "results": results},
            "messages": [{"role": "assistant", "content": msg, "stage": "mermaid_render"}]
        }
        
    except Exception as e:
        logger.warning(f"Mermaid rendering failed: {e}")
        return {
            "current_stage": "development",
            "mermaid_results": {"error": str(e)},
            "messages": [{"role": "warning", "content": f"⚠️ Mermaid rendering failed: {str(e)[:100]}", "stage": "mermaid_render"}]
        }


# ============================================================================
# NODE FUNCTIONS - DEVELOPMENT
# ============================================================================

async def development_node(state: PipelineGraphState) -> dict:
    """Generate code using Developer agent."""
    agents = get_agents()
    developer = agents["developer"]
    
    context = AgentContext()
    context.project_name = state.get("project_name", "new-project")
    context.project_description = state.get("project_idea", "")
    context.requirements = state.get("requirements", {})
    context.epics = state.get("epics", [])
    context.stories = state.get("user_stories", [])
    context.architecture = state.get("architecture", {})
    
    try:
        arch_message = AgentMessage(
            from_agent=AgentRole.ARCHITECT,
            to_agent=AgentRole.DEVELOPER,
            content="Architecture designed",
            artifacts={"architecture": state.get("architecture", {})}
        )
        
        message = await developer.generate_code(context, arch_message)
        code = message.artifacts.get("code", {})
        files_count = len(code.get("files", [])) if isinstance(code, dict) else 0
        
        return {
            "current_stage": "development_approval",
            "code_artifacts": code,
            "messages": [{
                "role": "assistant",
                "content": f"💻 Developer generated {files_count} code files",
                "stage": "development",
                "agent": "developer"
            }],
            "pending_approval": {
                "stage": "development",
                "content": message.content[:2000] if message.content else "",
                "files_count": files_count,
            }
        }
    except Exception as e:
        return {
            "current_stage": "failed",
            "errors": [f"Code generation failed: {str(e)}"],
            "messages": [{"role": "error", "content": f"Error: {str(e)}", "stage": "development"}]
        }


async def development_approval_node(state: PipelineGraphState) -> dict:
    """Human-in-the-loop approval for code."""
    pending = state.get("pending_approval", {})
    
    response = interrupt({
        "type": "approval",
        "stage": "development",
        "message": f"💻 Please review the generated code ({pending.get('files_count', 0)} files).",
        "instructions": "Type 'approve' to continue, 'revise' to regenerate, or 'reject' to stop.",
    })
    
    return {
        "approval_response": response,
        "messages": [{"role": "human", "content": f"User: {response}", "stage": "development_approval"}]
    }


def route_after_development_approval(state: PipelineGraphState) -> str:
    response = str(state.get("approval_response", "")).lower().strip()
    if response in ("approve", "approved", "yes", "y", "ok"):
        return "github_push_confirm"
    elif response in ("revise", "revision", "edit", "redo"):
        return "development"
    else:
        return "failed"


# ============================================================================
# NODE FUNCTIONS - GITHUB PUSH
# ============================================================================

async def github_push_confirm_node(state: PipelineGraphState) -> dict:
    """Confirm whether to push code to GitHub."""
    github_client = get_github_client()
    
    # Check what we have configured
    mcp_url = os.getenv("GITHUB_MCP_URL", "")
    token = os.getenv("GITHUB_TOKEN", "")
    owner = os.getenv("GITHUB_OWNER", "")
    
    config_status = []
    if mcp_url:
        config_status.append(f"✅ MCP URL: {mcp_url[:30]}...")
    else:
        config_status.append("❌ GITHUB_MCP_URL not set")
    if token:
        config_status.append(f"✅ Token: {token[:10]}...")
    else:
        config_status.append("❌ GITHUB_TOKEN not set")
    if owner:
        config_status.append(f"✅ Owner: {owner}")
    else:
        config_status.append("⚠️ GITHUB_OWNER not set (will need to provide)")
    
    if github_client:
        config_status.append("✅ GitHub client initialized")
    else:
        config_status.append("❌ GitHub client failed to initialize")
    
    config_display = "\n".join(config_status)
    
    response = interrupt({
        "type": "confirmation",
        "stage": "github_push",
        "message": "🐙 Push code to GitHub and create a Pull Request?",
        "instructions": "Type 'yes' to push to GitHub, or 'skip' to finish without pushing.",
        "configuration": config_display,
        "note": "Repository will be created automatically if it doesn't exist.",
    })
    
    response_str = _get_response_str(response)
    
    return {
        "confirmation_response": response_str,
        "messages": [{"role": "human", "content": f"User: {response_str}", "stage": "github_push_confirm"}]
    }


def route_after_github_push_confirm(state: PipelineGraphState) -> str:
    response = _get_response_str(state.get("confirmation_response", "")).lower()
    if response in ("yes", "y", "push", "ok", "approve"):
        return "github_push_input"
    else:
        return "completed"


async def github_push_input_node(state: PipelineGraphState) -> dict:
    """Collect inputs for GitHub push - separate prompts for each field."""
    project_name = state.get("project_name", "new-project")
    github_owner = os.getenv("GITHUB_OWNER", "")
    
    # Prompt for owner
    owner_response = interrupt({
        "type": "input",
        "stage": "github_push_input_owner",
        "message": "🐙 Step 1/3: Enter GitHub Owner/Organization",
        "instructions": f"Enter the repository owner or organization name.",
        "default": github_owner if github_owner else "your-username",
    })
    
    owner = _get_response_str(owner_response) or github_owner or "user"
    
    return {
        "github_inputs": {"owner": owner, "project_name": project_name},
        "messages": [{"role": "human", "content": f"GitHub Owner: {owner}", "stage": "github_push_input"}]
    }


async def github_push_input_repo_node(state: PipelineGraphState) -> dict:
    """Input: Repository name."""
    project_name = state.get("project_name", "new-project")
    existing_inputs = state.get("github_inputs", {})
    
    repo_response = interrupt({
        "type": "input",
        "stage": "github_push_input_repo",
        "message": "🐙 Step 2/3: Enter Repository Name",
        "instructions": f"Enter the repository name (will be created if doesn't exist).",
        "default": project_name,
    })
    
    repo = _get_response_str(repo_response) or project_name
    existing_inputs["repo"] = repo
    
    return {
        "github_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Repository: {repo}", "stage": "github_push_input_repo"}]
    }


async def github_push_input_branch_node(state: PipelineGraphState) -> dict:
    """Input: Branch name."""
    project_name = state.get("project_name", "new-project")
    existing_inputs = state.get("github_inputs", {})
    
    # Clean project name for branch (remove leading slashes, spaces)
    clean_name = project_name.strip().lstrip("/").replace(" ", "-")
    default_branch = f"feature/{clean_name}"
    
    branch_response = interrupt({
        "type": "input",
        "stage": "github_push_input_branch",
        "message": "🐙 Step 3/3: Enter Branch Name",
        "instructions": f"Enter the branch name to push to.",
        "default": default_branch,
    })
    
    branch = _get_response_str(branch_response) or default_branch
    
    # Clean branch name - remove double slashes
    while "//" in branch:
        branch = branch.replace("//", "/")
    branch = branch.strip().lstrip("/")
    
    existing_inputs["branch"] = branch
    
    return {
        "github_inputs": existing_inputs,
        "messages": [{"role": "human", "content": f"Branch: {branch}", "stage": "github_push_input_branch"}]
    }


async def github_push_node(state: PipelineGraphState) -> dict:
    """Push code to GitHub - creates repo, branch, pushes files, creates PR."""
    import asyncio
    
    github_client = get_github_client()
    inputs = state.get("github_inputs", {})
    
    if not github_client:
        return {
            "current_stage": "completed",
            "github_results": {"skipped": True, "reason": "GitHub client not configured"},
            "messages": [{"role": "warning", "content": "⚠️ GitHub client not configured", "stage": "github_push"}]
        }
    
    # Gather context
    project_name = state.get("project_name", "new-project")
    project_idea = state.get("project_idea", "")
    owner = inputs.get("owner", os.getenv("GITHUB_OWNER", "user"))
    repo = inputs.get("repo", project_name)
    branch = inputs.get("branch", f"feature/{project_name}").replace("//", "/").strip("/")
    
    # Get code files
    code = state.get("code_artifacts", {})
    files_to_push = []
    if isinstance(code, dict) and "files" in code:
        for file_info in code["files"]:
            path = file_info.get("path", "")
            content = file_info.get("content", "")
            if path and content:
                files_to_push.append({"path": path, "content": content})
    
    if not files_to_push:
        return {
            "current_stage": "completed",
            "github_results": {"error": "No code files to push"},
            "messages": [{"role": "warning", "content": "⚠️ No code files found", "stage": "github_push"}]
        }
    
    print(f"[DEBUG] GitHub Push: owner={owner}, repo={repo}, branch={branch}, files={len(files_to_push)}")
    
    results = []
    
    try:
        # Step 1: Create repository (with autoInit to create main branch)
        print(f"[DEBUG] Step 1: Creating repository {owner}/{repo}...")
        try:
            create_result = await github_client.call_tool("create_repository", {
                "name": repo,
                "description": f"SDLC Pipeline: {project_name}",
                "private": False,
                "autoInit": True,  # CORRECT: camelCase, creates README and main branch
            })
            print(f"[DEBUG] create_repository result: {create_result}")
            results.append({"step": "create_repo", "status": "success", "result": create_result})
            
            # Wait for GitHub to initialize the repo
            print("[DEBUG] Waiting 3s for GitHub to initialize repo...")
            await asyncio.sleep(3)
            
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] create_repository error: {error_str}")
            if "already exists" in error_str.lower() or "name already exists" in error_str.lower():
                results.append({"step": "create_repo", "status": "skipped", "reason": "Already exists"})
            else:
                # Check if error response indicates repo exists
                results.append({"step": "create_repo", "status": "warning", "error": error_str[:200]})
        
        # Step 2: Create the feature branch from main
        print(f"[DEBUG] Step 2: Creating branch {branch} from main...")
        try:
            branch_result = await github_client.call_tool("create_branch", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "from_branch": "main",
            })
            print(f"[DEBUG] create_branch result: {branch_result}")
            results.append({"step": "create_branch", "status": "success", "result": branch_result})
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] create_branch error: {error_str}")
            if "already exists" in error_str.lower() or "reference already exists" in error_str.lower():
                results.append({"step": "create_branch", "status": "skipped", "reason": "Already exists"})
            else:
                results.append({"step": "create_branch", "status": "warning", "error": error_str[:200]})
        
        # Step 3: Push files to the branch
        print(f"[DEBUG] Step 3: Pushing {len(files_to_push)} files to {branch}...")
        try:
            push_result = await github_client.call_tool("push_files", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "files": files_to_push,
                "message": f"feat: Initial implementation of {project_name}\n\nGenerated by SDLC Pipeline",
            })
            print(f"[DEBUG] push_files result: {push_result}")
            results.append({"step": "push_files", "status": "success", "result": push_result})
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] push_files error: {error_str}")
            results.append({"step": "push_files", "status": "error", "error": error_str[:200]})
            return {
                "current_stage": "completed",
                "github_results": {"results": results, "error": error_str},
                "messages": [{"role": "warning", "content": f"⚠️ Failed to push files: {error_str[:100]}", "stage": "github_push"}]
            }
        
        # Step 4: Create Pull Request
        print(f"[DEBUG] Step 4: Creating PR from {branch} to main...")
        pr_url = ""
        pr_number = ""
        try:
            pr_body = f"""## {project_name}

Auto-generated implementation from SDLC Pipeline.

### Files Changed
{chr(10).join(f'- `{f["path"]}`' for f in files_to_push[:20])}
{'...' if len(files_to_push) > 20 else ''}

---
*Generated by SDLC Pipeline with LangGraph Studio*
"""
            pr_result = await github_client.call_tool("create_pull_request", {
                "owner": owner,
                "repo": repo,
                "title": f"feat: {project_name} implementation",
                "body": pr_body,
                "head": branch,
                "base": "main",
            })
            print(f"[DEBUG] create_pull_request result: {pr_result}")
            results.append({"step": "create_pr", "status": "success", "result": pr_result})
            
            # Extract PR URL from result
            if isinstance(pr_result, dict):
                pr_url = pr_result.get("html_url") or pr_result.get("url") or ""
                pr_number = pr_result.get("number") or ""
                # Sometimes the result is in "text" field as JSON
                if not pr_url and "text" in pr_result:
                    try:
                        import json
                        text_data = json.loads(pr_result["text"]) if isinstance(pr_result["text"], str) else pr_result["text"]
                        pr_url = text_data.get("html_url") or text_data.get("url") or ""
                        pr_number = text_data.get("number") or ""
                    except:
                        pass
                        
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] create_pull_request error: {error_str}")
            results.append({"step": "create_pr", "status": "error", "error": error_str[:200]})
        
        # Build success message
        repo_url = f"https://github.com/{owner}/{repo}"
        msg_lines = [
            f"✅ Code pushed to GitHub!",
            f"  • Repository: {repo_url}",
            f"  • Branch: {branch}",
            f"  • Files: {len(files_to_push)}",
        ]
        if pr_url:
            msg_lines.append(f"  • PR: #{pr_number} {pr_url}")
        elif pr_number:
            msg_lines.append(f"  • PR: #{pr_number}")
        
        # Add any warnings
        warnings = [r for r in results if r.get("status") == "warning"]
        if warnings:
            msg_lines.append(f"\n⚠️ Warnings: {len(warnings)}")
        
        return {
            "current_stage": "completed",
            "github_results": {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "files_pushed": len(files_to_push),
                "pr_url": pr_url,
                "pr_number": pr_number,
                "results": results,
            },
            "messages": [{"role": "assistant", "content": "\n".join(msg_lines), "stage": "github_push"}]
        }
        
    except Exception as e:
        print(f"[DEBUG] GitHub push exception: {e}")
        import traceback
        traceback.print_exc()
        return {
            "current_stage": "completed",
            "github_results": {"error": str(e), "results": results},
            "messages": [{"role": "warning", "content": f"⚠️ GitHub error: {str(e)[:100]}", "stage": "github_push"}]
        }


# ============================================================================
# NODE FUNCTIONS - TERMINAL
# ============================================================================

async def completed_node(state: PipelineGraphState) -> dict:
    """Pipeline completed successfully."""
    project_name = state.get("project_name", "project")
    
    summary_parts = [f"🎉 SDLC Pipeline completed for '{project_name}'!"]
    
    if state.get("epics"):
        summary_parts.append(f"📝 {len(state['epics'])} Epics created")
    if state.get("user_stories"):
        summary_parts.append(f"📝 {len(state['user_stories'])} User Stories created")
    if state.get("ado_results") and not state["ado_results"].get("error"):
        summary_parts.append("☁️ Pushed to Azure DevOps")
    if state.get("ado_test_plan") and not state["ado_test_plan"].get("error"):
        summary_parts.append("🧪 Test Plan created")
    if state.get("architecture"):
        summary_parts.append(f"🏗️ Architecture with {len(state['architecture'].get('components', []))} components")
    if state.get("code_artifacts"):
        files = state["code_artifacts"].get("files", [])
        summary_parts.append(f"💻 {len(files)} code files generated")
    if state.get("github_pr") and not state["github_pr"].get("error"):
        summary_parts.append("🐙 GitHub PR created")
    
    return {
        "current_stage": "completed",
        "messages": [{"role": "system", "content": "\n".join(summary_parts), "stage": "completed"}]
    }


async def failed_node(state: PipelineGraphState) -> dict:
    """Pipeline failed."""
    errors = state.get("errors", [])
    return {
        "current_stage": "failed",
        "messages": [{"role": "error", "content": f"❌ Pipeline failed: {'; '.join(errors) if errors else 'Unknown error'}", "stage": "failed"}]
    }


# ============================================================================
# BUILD THE GRAPH
# ============================================================================

def build_graph():
    """Build the complete SDLC Pipeline LangGraph."""
    
    builder = StateGraph(PipelineGraphState)
    
    # Add all nodes
    builder.add_node("initialize", initialize_node)
    
    # Requirements stage
    builder.add_node("requirements", requirements_node)
    builder.add_node("requirements_approval", requirements_approval_node)
    
    # Work Items stage
    builder.add_node("work_items", work_items_node)
    builder.add_node("work_items_approval", work_items_approval_node)
    
    # ADO Push stage
    builder.add_node("ado_push_confirm", ado_push_confirm_node)
    builder.add_node("ado_push", ado_push_node)
    
    # Test Plan stage (multi-step)
    builder.add_node("test_plan_confirm", test_plan_confirm_node)
    builder.add_node("test_plan_input_name", test_plan_input_name_node)
    builder.add_node("test_plan_input_iteration", test_plan_input_iteration_node)
    builder.add_node("test_plan_input_description", test_plan_input_description_node)
    builder.add_node("test_plan_input_existing", test_plan_input_existing_node)
    builder.add_node("test_plan_input_suite", test_plan_input_suite_node)
    builder.add_node("test_plan_input_iteration_existing", test_plan_input_iteration_existing_node)
    builder.add_node("test_plan", test_plan_node)
    
    # Architecture stage
    builder.add_node("architecture", architecture_node)
    builder.add_node("architecture_approval", architecture_approval_node)
    
    # Mermaid Render stage
    builder.add_node("mermaid_render_confirm", mermaid_render_confirm_node)
    builder.add_node("mermaid_render", mermaid_render_node)
    
    # Development stage
    builder.add_node("development", development_node)
    builder.add_node("development_approval", development_approval_node)
    
    # GitHub Push stage (multi-step)
    builder.add_node("github_push_confirm", github_push_confirm_node)
    builder.add_node("github_push_input", github_push_input_node)
    builder.add_node("github_push_input_repo", github_push_input_repo_node)
    builder.add_node("github_push_input_branch", github_push_input_branch_node)
    builder.add_node("github_push", github_push_node)
    
    # Terminal nodes
    builder.add_node("completed", completed_node)
    builder.add_node("failed", failed_node)
    
    # ========== EDGES ==========
    
    # Start -> Initialize -> Requirements
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "requirements")
    builder.add_edge("requirements", "requirements_approval")
    
    builder.add_conditional_edges(
        "requirements_approval",
        route_after_requirements_approval,
        {"work_items": "work_items", "requirements": "requirements", "failed": "failed"}
    )
    
    # Work Items -> Approval -> ADO Push
    builder.add_edge("work_items", "work_items_approval")
    
    builder.add_conditional_edges(
        "work_items_approval",
        route_after_work_items_approval,
        {"ado_push_confirm": "ado_push_confirm", "work_items": "work_items", "failed": "failed"}
    )
    
    # ADO Push flow
    builder.add_conditional_edges(
        "ado_push_confirm",
        route_after_ado_push_confirm,
        {"ado_push": "ado_push", "test_plan_confirm": "test_plan_confirm"}
    )
    builder.add_edge("ado_push", "test_plan_confirm")
    
    # Test Plan flow (multi-step)
    builder.add_conditional_edges(
        "test_plan_confirm",
        route_after_test_plan_confirm,
        {"test_plan_input_name": "test_plan_input_name", "test_plan_input_existing": "test_plan_input_existing", "architecture": "architecture"}
    )
    
    # NEW plan flow: name -> iteration -> description -> test_plan
    builder.add_edge("test_plan_input_name", "test_plan_input_iteration")
    
    builder.add_conditional_edges(
        "test_plan_input_iteration",
        route_after_test_plan_input_iteration,
        {"test_plan_input_description": "test_plan_input_description", "architecture": "architecture"}
    )
    
    builder.add_conditional_edges(
        "test_plan_input_description",
        route_after_test_plan_input_description,
        {"test_plan": "test_plan", "architecture": "architecture"}
    )
    
    # EXISTING plan flow: plan_id -> suite_id -> iteration -> test_plan
    builder.add_conditional_edges(
        "test_plan_input_existing",
        route_after_test_plan_input_existing,
        {"test_plan_input_suite": "test_plan_input_suite", "architecture": "architecture"}
    )
    
    builder.add_conditional_edges(
        "test_plan_input_suite",
        route_after_test_plan_input_suite,
        {"test_plan_input_iteration_existing": "test_plan_input_iteration_existing", "architecture": "architecture"}
    )
    
    builder.add_conditional_edges(
        "test_plan_input_iteration_existing",
        route_after_test_plan_input_iteration_existing,
        {"test_plan": "test_plan", "architecture": "architecture"}
    )
    
    builder.add_edge("test_plan", "architecture")
    
    # Architecture -> Approval -> Mermaid
    builder.add_edge("architecture", "architecture_approval")
    
    builder.add_conditional_edges(
        "architecture_approval",
        route_after_architecture_approval,
        {"mermaid_render_confirm": "mermaid_render_confirm", "architecture": "architecture", "failed": "failed"}
    )
    
    # Mermaid flow
    builder.add_conditional_edges(
        "mermaid_render_confirm",
        route_after_mermaid_render_confirm,
        {"mermaid_render": "mermaid_render", "development": "development"}
    )
    builder.add_edge("mermaid_render", "development")
    
    # Development -> Approval -> GitHub Push
    builder.add_edge("development", "development_approval")
    
    builder.add_conditional_edges(
        "development_approval",
        route_after_development_approval,
        {"github_push_confirm": "github_push_confirm", "development": "development", "failed": "failed"}
    )
    
    # GitHub Push flow (multi-step)
    builder.add_conditional_edges(
        "github_push_confirm",
        route_after_github_push_confirm,
        {"github_push_input": "github_push_input", "completed": "completed"}
    )
    builder.add_edge("github_push_input", "github_push_input_repo")
    builder.add_edge("github_push_input_repo", "github_push_input_branch")
    builder.add_edge("github_push_input_branch", "github_push")
    builder.add_edge("github_push", "completed")
    
    # Terminal edges
    builder.add_edge("completed", END)
    builder.add_edge("failed", END)
    
    # Compile without checkpointer (Studio handles persistence)
    return builder.compile(
        interrupt_before=[
            "requirements_approval",
            "work_items_approval",
            "ado_push_confirm",
            "test_plan_confirm",
            "test_plan_input_name",
            "test_plan_input_iteration",
            "test_plan_input_description",
            "test_plan_input_existing",
            "test_plan_input_suite",
            "test_plan_input_iteration_existing",
            "architecture_approval",
            "mermaid_render_confirm",
            "development_approval",
            "github_push_confirm",
            "github_push_input",
            "github_push_input_repo",
            "github_push_input_branch",
        ]
    )


# Export the compiled graph for LangGraph Studio
graph = build_graph()