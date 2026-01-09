"""
SDLC Pipeline - Fully Agentic LangGraph Implementation

Each stage uses ReAct pattern: Reason → Act → Observe → Adapt
LLM agents have access to tools and can reason about how to accomplish tasks.
"""

import asyncio
import json
import logging
import os
from typing import Annotated, Any, Callable

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt, Command
from typing_extensions import TypedDict

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# STATE DEFINITION
# ============================================================================

def messages_reducer(left: list, right: list) -> list:
    """Merge message lists, avoiding duplicates."""
    if not left:
        return right
    if not right:
        return left
    return left + right


class PipelineState(TypedDict, total=False):
    """State for the agentic SDLC pipeline."""
    # Input
    project_idea: str
    project_name: str
    
    # Conversation messages for each agent
    messages: Annotated[list, add_messages]
    
    # Stage outputs (structured)
    requirements: dict | None
    epics: list | None
    user_stories: list | None
    architecture: dict | None
    code_artifacts: dict | None
    
    # Integration results
    ado_results: dict | None
    ado_test_plan: dict | None
    github_results: dict | None
    github_inputs: dict | None
    mermaid_results: dict | None
    
    # Human-in-loop
    human_feedback: str | None
    pending_approval: str | None
    
    # Flow control
    current_stage: str
    errors: list


# ============================================================================
# MCP CLIENT INITIALIZATION
# ============================================================================

_ado_client = None
_github_client = None


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


# ============================================================================
# TOOL DEFINITIONS - These are what agents can use
# ============================================================================

@tool
def save_requirements(requirements: dict) -> str:
    """Save generated requirements to state. Call this when requirements are complete."""
    return json.dumps({"status": "saved", "count": len(requirements.get("functional", []))})


@tool
def save_work_items(epics: list, stories: list) -> str:
    """Save generated epics and user stories to state."""
    return json.dumps({"status": "saved", "epics": len(epics), "stories": len(stories)})


@tool
def save_architecture(architecture: dict) -> str:
    """Save architecture design to state."""
    return json.dumps({"status": "saved", "components": len(architecture.get("components", []))})


@tool
def save_code(files: list) -> str:
    """Save generated code files to state."""
    return json.dumps({"status": "saved", "files": len(files)})


@tool
async def ado_create_work_item(work_item_type: str, title: str, description: str = "", parent_id: int = None) -> str:
    """Create a work item in Azure DevOps. Types: Epic, Issue, Task, Bug."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        fields = {
            "System.Title": title,
            "System.Description": description,
        }
        if parent_id:
            fields["System.Parent"] = parent_id
            
        result = await client.call_tool("wit_create_work_item", {
            "project": client.project,
            "workItemType": work_item_type,
            "fields": fields,
        })
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def ado_list_iterations() -> str:
    """List available iteration paths in Azure DevOps project."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        result = await client.call_tool("work_list_iterations", {
            "project": client.project,
            "depth": 10,
        })
        
        # Extract paths
        paths = []
        def walk(n):
            if isinstance(n, dict):
                if "path" in n:
                    paths.append(n["path"])
                if "children" in n:
                    for c in n["children"]:
                        walk(c)
            elif isinstance(n, list):
                for item in n:
                    walk(item)
        walk(result)
        
        return json.dumps({"iterations": paths[:20]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def ado_create_test_plan(name: str, iteration: str, description: str = "") -> str:
    """Create a test plan in Azure DevOps."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        result = await client.create_test_plan(
            name=name,
            iteration=iteration,
            description=description,
        )
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def ado_create_test_suite(plan_id: int, name: str) -> str:
    """Create a test suite under a test plan."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        result = await client.create_test_suite(
            plan_id=plan_id,
            parent_suite_id=plan_id,
            name=name,
        )
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def ado_create_test_case(title: str, steps: str, iteration_path: str) -> str:
    """Create a test case in Azure DevOps."""
    client = get_ado_client()
    if not client:
        return json.dumps({"error": "ADO client not configured"})
    
    try:
        result = await client.create_test_case(
            title=title,
            steps=steps,
            priority=2,
            iteration_path=iteration_path,
        )
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def github_create_repo(name: str, description: str = "", private: bool = False) -> str:
    """Create a new GitHub repository with autoInit to create main branch."""
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        result = await client.call_tool("create_repository", {
            "name": name,
            "description": description,
            "private": private,
            "autoInit": True,  # CORRECT: camelCase, creates README and main branch
        })
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        if "already exists" in str(e).lower():
            return json.dumps({"status": "exists", "message": "Repository already exists"})
        return json.dumps({"error": str(e)})


@tool
async def github_create_branch(owner: str, repo: str, branch: str, from_branch: str = "main") -> str:
    """Create a new branch in a GitHub repository."""
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        result = await client.call_tool("create_branch", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "from_branch": from_branch,
        })
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        if "already exists" in str(e).lower() or "reference already exists" in str(e).lower():
            return json.dumps({"status": "exists", "message": "Branch already exists"})
        return json.dumps({"error": str(e)})


@tool
async def github_push_files(owner: str, repo: str, branch: str, files: list, message: str) -> str:
    """Push files to a GitHub repository. Files should be list of {path, content} dicts."""
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        result = await client.call_tool("push_files", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "files": files,
            "message": message,
        })
        return json.dumps({"status": "pushed", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def github_create_pr(owner: str, repo: str, title: str, body: str, head: str, base: str = "main") -> str:
    """Create a pull request on GitHub."""
    client = get_github_client()
    if not client:
        return json.dumps({"error": "GitHub client not configured"})
    
    try:
        result = await client.call_tool("create_pull_request", {
            "owner": owner,
            "repo": repo,
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        })
        return json.dumps({"status": "created", "result": str(result)[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
async def render_mermaid_diagram(diagram_code: str, output_path: str) -> str:
    """Render a Mermaid diagram to PNG file."""
    import asyncio
    import concurrent.futures
    
    def render_sync():
        """Run blocking render in thread."""
        try:
            import os
            os.makedirs(os.path.dirname(output_path) or "docs/diagrams", exist_ok=True)
            
            from src.mcp_client import MermaidMCPClient
            client = MermaidMCPClient()
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(client.render_mermaid_to_file(diagram_code, output_path))
            finally:
                loop.close()
            
            return {"status": "rendered", "path": output_path}
        except Exception as e:
            return {"error": str(e)}
    
    try:
        # Run in thread pool to avoid blocking
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(executor, render_sync)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# LLM CONFIGURATION
# ============================================================================

def get_llm():
    """Get configured LLM."""
    return ChatOpenAI(
        model=os.getenv("SDLC_MODEL_DEFAULT", "gpt-4o"),
        temperature=0.1,
    )


# ============================================================================
# AGENT FACTORY - Creates ReAct agents for each stage
# ============================================================================

def create_agent_node(
    name: str,
    system_prompt: str,
    tools: list,
    output_parser: Callable[[Any], dict] = None,
):
    """
    Create a ReAct agent node that can reason and use tools.
    
    The agent will:
    1. Receive context from state
    2. Reason about what to do
    3. Use tools as needed
    4. Return structured output
    """
    
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools) if tools else llm
    
    async def agent_node(state: PipelineState) -> dict:
        """Execute the agent."""
        messages = state.get("messages", [])
        
        # Add system prompt if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        
        # Invoke LLM
        response = await llm_with_tools.ainvoke(messages)
        
        # Check if agent wants to use tools
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Execute tools
            tool_results = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Find and execute the tool
                for t in tools:
                    if t.name == tool_name:
                        try:
                            if asyncio.iscoroutinefunction(t.func):
                                result = await t.func(**tool_args)
                            else:
                                result = t.func(**tool_args)
                            tool_results.append(ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call["id"],
                            ))
                        except Exception as e:
                            tool_results.append(ToolMessage(
                                content=json.dumps({"error": str(e)}),
                                tool_call_id=tool_call["id"],
                            ))
                        break
            
            # Continue conversation with tool results
            messages = messages + [response] + tool_results
            response = await llm_with_tools.ainvoke(messages)
        
        # Parse output if parser provided
        output = {"messages": messages + [response]}
        if output_parser:
            try:
                parsed = output_parser(response.content)
                output.update(parsed)
            except Exception as e:
                logger.warning(f"Could not parse output: {e}")
        
        return output
    
    return agent_node


# ============================================================================
# STAGE-SPECIFIC AGENTS
# ============================================================================

# Requirements Agent
requirements_tools = [save_requirements]
requirements_prompt = """You are a Product Manager AI agent. Your job is to analyze a project idea and generate comprehensive software requirements.

Given the project idea, you must:
1. Identify functional requirements (features the system must have)
2. Identify non-functional requirements (performance, security, scalability)
3. Define acceptance criteria for each requirement
4. Prioritize requirements (P1=critical, P2=important, P3=nice-to-have)

Output your requirements in a structured format, then call save_requirements() to store them.

Be thorough but practical. Focus on MVP requirements first."""


def parse_requirements(content: str) -> dict:
    """Extract requirements from LLM response."""
    try:
        # Try to find JSON in response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
            return {"requirements": json.loads(json_str)}
        elif "{" in content and "}" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            return {"requirements": json.loads(content[start:end])}
    except:
        pass
    return {"requirements": {"raw": content}}


# Work Items Agent (BA)
work_items_tools = [save_work_items, ado_create_work_item]
work_items_prompt = """You are a Business Analyst AI agent. Your job is to convert requirements into actionable work items.

Given requirements, you must:
1. Create Epics for major feature areas
2. Break down Epics into User Stories with acceptance criteria
3. Estimate story points (1, 2, 3, 5, 8, 13)
4. Prioritize stories within each epic

For each story, use the format:
"As a [user], I want [feature], so that [benefit]"

After generating work items, you can optionally push them to Azure DevOps using the ado_create_work_item tool.
Call save_work_items() when done to store them in state."""


def parse_work_items(content: str) -> dict:
    """Extract work items from LLM response."""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
            data = json.loads(json_str)
            return {"epics": data.get("epics", []), "user_stories": data.get("stories", [])}
    except:
        pass
    return {}


# Architecture Agent
architecture_tools = [save_architecture, render_mermaid_diagram]
architecture_prompt = """You are a Software Architect AI agent. Your job is to design the technical architecture.

Given requirements and work items, you must:
1. Define system components and their responsibilities
2. Design the data model (entities, relationships)
3. Specify APIs and interfaces
4. Choose technology stack
5. Create architecture diagrams in Mermaid format:
   - C4 Context diagram
   - C4 Container diagram
   - Sequence diagrams for key flows

Include diagrams as Mermaid code. You can use render_mermaid_diagram() to create PNG files.
Call save_architecture() when done."""


def parse_architecture(content: str) -> dict:
    """Extract architecture from LLM response."""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
            return {"architecture": json.loads(json_str)}
    except:
        pass
    return {}


# Developer Agent
developer_tools = [save_code, github_create_repo, github_create_branch, github_push_files, github_create_pr]
developer_prompt = """You are a Senior Developer AI agent. Your job is to implement the architecture.

Given architecture and requirements, you must:
1. Generate production-quality code for each component
2. Follow best practices and design patterns
3. Include proper error handling and logging
4. Write unit tests for critical paths
5. Create configuration files (docker, CI/CD, etc.)

Generate complete, runnable code files. Call save_code() with the list of files.

You can also push code to GitHub using this EXACT sequence:
1. Use github_create_repo() to create the repository (creates main branch automatically)
2. Wait a moment, then use github_create_branch() to create a feature branch from main
3. Use github_push_files() to push all code files to the feature branch
4. Use github_create_pr() to create a pull request from feature branch to main

IMPORTANT: You MUST create the branch before pushing files to it!"""


def parse_code(content: str) -> dict:
    """Extract code files from LLM response."""
    files = []
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
            data = json.loads(json_str)
            if "files" in data:
                files = data["files"]
    except:
        pass
    return {"code_artifacts": {"files": files}} if files else {}


# Test Plan Agent
test_plan_tools = [ado_list_iterations, ado_create_test_plan, ado_create_test_suite, ado_create_test_case]
test_plan_prompt = """You are a QA Engineer AI agent. Your job is to create a comprehensive test plan.

Given user stories, you must:
1. First, call ado_list_iterations() to see available iteration paths
2. Create a test plan using ado_create_test_plan()
3. Create test suites for each feature area
4. Generate test cases from user story acceptance criteria
5. Each test case should have clear steps and expected results

Format test steps as: "step_number. action|expected_result"

Work systematically through each user story to ensure complete test coverage."""


# ============================================================================
# HUMAN-IN-THE-LOOP NODES
# ============================================================================

async def human_approval_node(state: PipelineState) -> dict:
    """Request human approval before proceeding."""
    stage = state.get("current_stage", "unknown")
    
    response = interrupt({
        "type": "approval",
        "stage": stage,
        "message": f"Please review the {stage} output.",
        "instructions": "Type 'approve' to continue, 'revise' to regenerate, or 'reject' to stop.",
    })
    
    return {
        "human_feedback": response,
        "messages": [HumanMessage(content=f"Human feedback: {response}")],
    }


def route_after_approval(state: PipelineState) -> str:
    """Route based on human feedback."""
    feedback = str(state.get("human_feedback", "")).lower().strip()
    stage = state.get("current_stage", "")
    
    if feedback in ("approve", "approved", "yes", "y", "ok"):
        # Map to next stage
        stage_flow = {
            "requirements": "work_items",
            "work_items": "ado_push",
            "ado_push": "test_plan",
            "test_plan": "architecture",
            "architecture": "development",
            "development": "github_push_confirm",  # Go to confirm first
            "github_push": "completed",
        }
        return stage_flow.get(stage, "completed")
    elif feedback in ("revise", "revision", "edit", "redo"):
        return stage  # Loop back
    else:
        return "failed"


# ============================================================================
# BUILD THE GRAPH
# ============================================================================

def build_graph():
    """Build the agentic SDLC pipeline graph."""
    
    builder = StateGraph(PipelineState)
    
    # Create agent nodes
    requirements_agent = create_agent_node(
        "requirements",
        requirements_prompt,
        requirements_tools,
        parse_requirements,
    )
    
    work_items_agent = create_agent_node(
        "work_items",
        work_items_prompt,
        work_items_tools,
        parse_work_items,
    )
    
    architecture_agent = create_agent_node(
        "architecture",
        architecture_prompt,
        architecture_tools,
        parse_architecture,
    )
    
    developer_agent = create_agent_node(
        "developer",
        developer_prompt,
        developer_tools,
        parse_code,
    )
    
    test_plan_agent = create_agent_node(
        "test_plan",
        test_plan_prompt,
        test_plan_tools,
        None,
    )
    
    # Initialize node
    async def initialize(state: PipelineState) -> dict:
        project_idea = state.get("project_idea", "")
        project_name = state.get("project_name", "new-project")
        return {
            "current_stage": "requirements",
            "messages": [
                HumanMessage(content=f"Project: {project_name}\n\nIdea: {project_idea}\n\nPlease generate comprehensive requirements.")
            ],
        }
    
    # Stage wrapper nodes (set current_stage)
    async def requirements_node(state: PipelineState) -> dict:
        result = await requirements_agent(state)
        result["current_stage"] = "requirements"
        return result
    
    async def work_items_node(state: PipelineState) -> dict:
        # Add context from previous stage
        reqs = state.get("requirements", {})
        state["messages"].append(HumanMessage(
            content=f"Requirements:\n{json.dumps(reqs, indent=2)[:2000]}\n\nCreate epics and user stories."
        ))
        result = await work_items_agent(state)
        result["current_stage"] = "work_items"
        return result
    
    async def ado_push_node(state: PipelineState) -> dict:
        """Push work items to ADO using agent."""
        epics = state.get("epics", [])
        stories = state.get("user_stories", [])
        
        if not get_ado_client():
            return {
                "current_stage": "ado_push",
                "ado_results": {"skipped": True, "reason": "ADO not configured"},
            }
        
        # Use agent to push
        agent = create_agent_node(
            "ado_push",
            "Push the work items to Azure DevOps. Create epics first, then stories under each epic.",
            [ado_create_work_item],
            None,
        )
        
        state["messages"].append(HumanMessage(
            content=f"Push these to ADO:\nEpics: {json.dumps(epics[:5], indent=2)}\nStories: {json.dumps(stories[:10], indent=2)}"
        ))
        
        result = await agent(state)
        result["current_stage"] = "ado_push"
        return result
    
    async def test_plan_node(state: PipelineState) -> dict:
        stories = state.get("user_stories", [])
        state["messages"].append(HumanMessage(
            content=f"Create test plan for these stories:\n{json.dumps(stories[:10], indent=2)}"
        ))
        result = await test_plan_agent(state)
        result["current_stage"] = "test_plan"
        return result
    
    async def architecture_node(state: PipelineState) -> dict:
        reqs = state.get("requirements", {})
        stories = state.get("user_stories", [])
        state["messages"].append(HumanMessage(
            content=f"Design architecture for:\nRequirements: {json.dumps(reqs, indent=2)[:1500]}\nStories: {json.dumps(stories[:5], indent=2)}"
        ))
        result = await architecture_agent(state)
        result["current_stage"] = "architecture"
        return result
    
    async def development_node(state: PipelineState) -> dict:
        arch = state.get("architecture", {})
        reqs = state.get("requirements", {})
        state["messages"].append(HumanMessage(
            content=f"Implement this architecture:\n{json.dumps(arch, indent=2)[:2000]}"
        ))
        result = await developer_agent(state)
        result["current_stage"] = "development"
        return result
    
    async def github_push_confirm_node(state: PipelineState) -> dict:
        """Confirm and collect inputs for GitHub push."""
        project_name = state.get("project_name", "new-project")
        owner = os.getenv("GITHUB_OWNER", "")
        
        github_client = get_github_client()
        config_status = "✅ GitHub client ready" if github_client else "❌ GitHub client not configured"
        
        response = interrupt({
            "type": "github_input",
            "message": "🐙 Push code to GitHub?",
            "instructions": "Enter owner, repo name, and branch (or 'skip' to finish without pushing)",
            "config_status": config_status,
            "defaults": {
                "owner": owner or "your-username",
                "repo": project_name,
                "branch": f"feature/{project_name}",
            },
            "note": "Repository will be created automatically if it doesn't exist.",
        })
        
        # Parse response
        if isinstance(response, str):
            response_lower = response.lower().strip()
            if response_lower in ("skip", "no", "n"):
                return {
                    "current_stage": "github_push_confirm",
                    "github_inputs": {"skip": True},
                    "messages": [HumanMessage(content="User skipped GitHub push")],
                }
            # If single string, might be just "yes" - use defaults
            if response_lower in ("yes", "y", "ok"):
                return {
                    "current_stage": "github_push_confirm",
                    "github_inputs": {
                        "owner": owner or "user",
                        "repo": project_name,
                        "branch": f"feature/{project_name}",
                    },
                    "messages": [HumanMessage(content=f"GitHub: {owner}/{project_name}")],
                }
        
        # Parse as dict if provided
        if isinstance(response, dict):
            return {
                "current_stage": "github_push_confirm",
                "github_inputs": response,
                "messages": [HumanMessage(content=f"GitHub inputs: {response}")],
            }
        
        return {
            "current_stage": "github_push_confirm",
            "github_inputs": {"skip": True},
            "messages": [HumanMessage(content="GitHub push skipped")],
        }
    
    def route_after_github_confirm(state: PipelineState) -> str:
        inputs = state.get("github_inputs", {})
        if inputs.get("skip"):
            return "completed"
        return "github_push"
    
    async def github_push_node(state: PipelineState) -> dict:
        """Push code to GitHub - creates repo, branch, pushes files, creates PR."""
        import asyncio as aio
        
        code = state.get("code_artifacts", {})
        project_name = state.get("project_name", "new-project")
        inputs = state.get("github_inputs", {})
        
        owner = inputs.get("owner") or os.getenv("GITHUB_OWNER", "user")
        repo = inputs.get("repo") or project_name
        branch = inputs.get("branch") or f"feature/{project_name}"
        branch = branch.replace("//", "/").strip("/")
        
        github_client = get_github_client()
        if not github_client:
            return {
                "current_stage": "github_push",
                "github_results": {"skipped": True, "reason": "GitHub not configured"},
                "messages": [AIMessage(content="⚠️ GitHub client not configured")],
            }
        
        # Get files to push
        files_to_push = []
        if isinstance(code, dict) and "files" in code:
            for f in code["files"]:
                if f.get("path") and f.get("content"):
                    files_to_push.append({"path": f["path"], "content": f["content"]})
        
        if not files_to_push:
            return {
                "current_stage": "github_push",
                "github_results": {"error": "No files to push"},
                "messages": [AIMessage(content="⚠️ No code files found to push")],
            }
        
        results = []
        
        # Step 1: Create repository
        try:
            result = await github_client.call_tool("create_repository", {
                "name": repo,
                "description": f"SDLC Pipeline: {project_name}",
                "private": False,
                "autoInit": True,
            })
            results.append({"step": "create_repo", "status": "success"})
            await aio.sleep(3)  # Wait for GitHub to initialize
        except Exception as e:
            if "already exists" in str(e).lower():
                results.append({"step": "create_repo", "status": "exists"})
            else:
                results.append({"step": "create_repo", "status": "error", "error": str(e)})
        
        # Step 2: Create branch
        try:
            result = await github_client.call_tool("create_branch", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "from_branch": "main",
            })
            results.append({"step": "create_branch", "status": "success"})
        except Exception as e:
            if "already exists" in str(e).lower():
                results.append({"step": "create_branch", "status": "exists"})
            else:
                results.append({"step": "create_branch", "status": "error", "error": str(e)})
        
        # Step 3: Push files
        try:
            result = await github_client.call_tool("push_files", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "files": files_to_push,
                "message": f"feat: {project_name} implementation",
            })
            results.append({"step": "push_files", "status": "success"})
        except Exception as e:
            results.append({"step": "push_files", "status": "error", "error": str(e)})
            return {
                "current_stage": "github_push",
                "github_results": {"error": str(e), "results": results},
                "messages": [AIMessage(content=f"⚠️ Push failed: {str(e)[:100]}")],
            }
        
        # Step 4: Create PR
        pr_url = ""
        try:
            result = await github_client.call_tool("create_pull_request", {
                "owner": owner,
                "repo": repo,
                "title": f"feat: {project_name}",
                "body": f"Implementation of {project_name}\n\nGenerated by SDLC Pipeline",
                "head": branch,
                "base": "main",
            })
            results.append({"step": "create_pr", "status": "success", "result": result})
            if isinstance(result, dict):
                pr_url = result.get("html_url") or result.get("url", "")
        except Exception as e:
            results.append({"step": "create_pr", "status": "error", "error": str(e)})
        
        msg = f"✅ Code pushed to GitHub!\n  • Repo: https://github.com/{owner}/{repo}\n  • Branch: {branch}\n  • Files: {len(files_to_push)}"
        if pr_url:
            msg += f"\n  • PR: {pr_url}"
        
        return {
            "current_stage": "github_push",
            "github_results": {"owner": owner, "repo": repo, "branch": branch, "results": results},
            "messages": [AIMessage(content=msg)],
        }
    
    async def completed_node(state: PipelineState) -> dict:
        return {
            "current_stage": "completed",
            "messages": [AIMessage(content="🎉 SDLC Pipeline completed successfully!")],
        }
    
    async def failed_node(state: PipelineState) -> dict:
        return {
            "current_stage": "failed",
            "messages": [AIMessage(content="❌ Pipeline stopped.")],
        }
    
    # Add nodes
    builder.add_node("initialize", initialize)
    builder.add_node("requirements", requirements_node)
    builder.add_node("requirements_approval", human_approval_node)
    builder.add_node("work_items", work_items_node)
    builder.add_node("work_items_approval", human_approval_node)
    builder.add_node("ado_push", ado_push_node)
    builder.add_node("test_plan", test_plan_node)
    builder.add_node("architecture", architecture_node)
    builder.add_node("architecture_approval", human_approval_node)
    builder.add_node("development", development_node)
    builder.add_node("development_approval", human_approval_node)
    builder.add_node("github_push_confirm", github_push_confirm_node)
    builder.add_node("github_push", github_push_node)
    builder.add_node("completed", completed_node)
    builder.add_node("failed", failed_node)
    
    # Add edges
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "requirements")
    builder.add_edge("requirements", "requirements_approval")
    
    builder.add_conditional_edges(
        "requirements_approval",
        route_after_approval,
        {"work_items": "work_items", "requirements": "requirements", "failed": "failed"}
    )
    
    builder.add_edge("work_items", "work_items_approval")
    
    builder.add_conditional_edges(
        "work_items_approval",
        route_after_approval,
        {"ado_push": "ado_push", "work_items": "work_items", "failed": "failed"}
    )
    
    builder.add_edge("ado_push", "test_plan")
    builder.add_edge("test_plan", "architecture")
    builder.add_edge("architecture", "architecture_approval")
    
    builder.add_conditional_edges(
        "architecture_approval",
        route_after_approval,
        {"development": "development", "architecture": "architecture", "failed": "failed"}
    )
    
    builder.add_edge("development", "development_approval")
    
    builder.add_conditional_edges(
        "development_approval",
        route_after_approval,
        {"github_push_confirm": "github_push_confirm", "development": "development", "failed": "failed"}
    )
    
    builder.add_conditional_edges(
        "github_push_confirm",
        route_after_github_confirm,
        {"github_push": "github_push", "completed": "completed"}
    )
    
    builder.add_edge("github_push", "completed")
    builder.add_edge("completed", END)
    builder.add_edge("failed", END)
    
    # Compile with interrupts
    return builder.compile(
        interrupt_before=[
            "requirements_approval",
            "work_items_approval",
            "architecture_approval",
            "development_approval",
            "github_push_confirm",
        ]
    )


# Export graph
graph = build_graph()