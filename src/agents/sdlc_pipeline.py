"""SDLC Pipeline Orchestrator - Multi-agent software development lifecycle pipeline."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from langchain_openai import ChatOpenAI
from langsmith import traceable

from src.agents.architect_agent import ArchitectAgent
from src.agents.base_agent import AgentContext, AgentMessage, AgentRole, ApprovalStatus
from src.agents.business_analyst_agent import BusinessAnalystAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.human_in_loop import HumanInTheLoop
from src.agents.product_manager_agent import ProductManagerAgent
from src.mcp_client.ado_client import AzureDevOpsMCPClient
from src.mcp_client.github_client import GitHubMCPClient

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """SDLC Pipeline stages."""

    INITIALIZATION = "initialization"
    REQUIREMENTS = "requirements"
    REQUIREMENTS_APPROVAL = "requirements_approval"
    WORK_ITEMS = "work_items"
    WORK_ITEMS_APPROVAL = "work_items_approval"
    ADO_PUSH = "ado_push"
    ARCHITECTURE = "architecture"
    ARCHITECTURE_APPROVAL = "architecture_approval"
    DEVELOPMENT = "development"
    DEVELOPMENT_APPROVAL = "development_approval"
    GITHUB_PUSH = "github_push"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineState:
    """State of the SDLC pipeline."""

    stage: PipelineStage = PipelineStage.INITIALIZATION
    context: AgentContext = field(default_factory=AgentContext)
    messages: list[AgentMessage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    revision_count: dict[str, int] = field(default_factory=dict)
    max_revisions: int = 3

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to the pipeline state."""
        self.messages.append(message)

    def get_last_message_from(self, agent: AgentRole) -> AgentMessage | None:
        """Get the last message from a specific agent."""
        for msg in reversed(self.messages):
            if msg.from_agent == agent:
                return msg
        return None


class SDLCPipelineOrchestrator:
    """Orchestrator for the multi-agent SDLC pipeline."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        github_client: GitHubMCPClient | None = None,
        ado_client: AzureDevOpsMCPClient | None = None,
        human_in_loop: HumanInTheLoop | None = None,
        interactive: bool = True,
    ):
        """Initialize the SDLC Pipeline Orchestrator.

        Args:
            llm: ChatOpenAI instance for agents.
            github_client: GitHub MCP client.
            ado_client: Azure DevOps MCP client.
            human_in_loop: Human-in-the-loop handler.
            interactive: Whether to prompt for human input.
        """
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0.7)
        self.github_client = github_client
        self.ado_client = ado_client
        self.hitl = human_in_loop or HumanInTheLoop(interactive=interactive)

        # Initialize agents with shared LLM
        self.product_manager = ProductManagerAgent(llm=self.llm)
        self.business_analyst = BusinessAnalystAgent(llm=self.llm, ado_client=ado_client)
        self.architect = ArchitectAgent(llm=self.llm)
        self.developer = DeveloperAgent(llm=self.llm, github_client=github_client)

        self.state = PipelineState()

    @traceable(name="sdlc_pipeline_run")
    async def run(
        self,
        project_idea: str,
        project_name: str | None = None,
    ) -> PipelineState:
        """Run the complete SDLC pipeline.

        Args:
            project_idea: High-level project idea or description.
            project_name: Optional project name.

        Returns:
            Final pipeline state.
        """
        logger.info(f"Starting SDLC Pipeline for: {project_idea[:100]}...")
        self.hitl.notify(f"Starting SDLC Pipeline for: {project_name or 'New Project'}", "info")

        try:
            # Initialize context
            self.state.context.project_name = project_name or "new-project"
            self.state.stage = PipelineStage.INITIALIZATION

            # Stage 1: Generate Requirements
            await self._run_requirements_stage(project_idea)

            # Stage 2: Create Work Items
            await self._run_work_items_stage()

            # Stage 3: Push to Azure DevOps
            await self._run_ado_push_stage()

            # Stage 4: Architecture Design
            await self._run_architecture_stage()

            # Stage 5: Development
            await self._run_development_stage()

            # Stage 6: Push to GitHub
            await self._run_github_push_stage()

            # Complete
            self.state.stage = PipelineStage.COMPLETED
            self.state.completed_at = datetime.now()
            self.hitl.notify("SDLC Pipeline completed successfully!", "success")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.state.stage = PipelineStage.FAILED
            self.state.errors.append(str(e))
            self.hitl.notify(f"Pipeline failed: {e}", "error")

        return self.state

    @traceable(name="requirements_stage")
    async def _run_requirements_stage(self, project_idea: str) -> None:
        """Run the requirements generation stage."""
        self.state.stage = PipelineStage.REQUIREMENTS
        self.hitl.display_progress("Requirements", 1, 6, "Generating requirements...")

        # Set project description from initial idea
        self.state.context.project_description = project_idea

        while True:
            # Generate requirements
            message = await self.product_manager.generate_requirements(
                self.state.context,
                domain=None,  # Could be extracted from project_idea
            )
            self.state.add_message(message)

            # Store requirements in context
            if "requirements" in message.artifacts:
                self.state.context.requirements = message.artifacts["requirements"]

            # Human approval
            self.state.stage = PipelineStage.REQUIREMENTS_APPROVAL
            approval = self.hitl.request_approval(message)
            message.approval_status = approval

            if approval == ApprovalStatus.APPROVED:
                break
            elif approval == ApprovalStatus.REJECTED:
                raise Exception("Requirements rejected by user")
            elif approval == ApprovalStatus.REVISION_REQUESTED:
                self._increment_revision("requirements")
                feedback = self.hitl.request_feedback(
                    "What changes would you like to the requirements?"
                )
                project_idea = f"{project_idea}\n\nUser Feedback: {feedback}"

        self.hitl.notify("Requirements approved!", "success")

    @traceable(name="work_items_stage")
    async def _run_work_items_stage(self) -> None:
        """Run the work items creation stage."""
        self.state.stage = PipelineStage.WORK_ITEMS
        self.hitl.display_progress("Work Items", 2, 6, "Creating Epics and Stories...")

        # Get the requirements message from PM
        requirements_message = self.state.get_last_message_from(AgentRole.PRODUCT_MANAGER)
        if not requirements_message:
            raise Exception("No requirements message found from Product Manager")

        while True:
            # Create work items
            message = await self.business_analyst.create_work_items(
                self.state.context,
                requirements_message,
            )
            self.state.add_message(message)

            # Store work items in context
            if "work_items" in message.artifacts:
                work_items = message.artifacts["work_items"]
                if "epics" in work_items:
                    self.state.context.epics = work_items["epics"]
                if "stories" in work_items:
                    self.state.context.stories = work_items["stories"]
            if "epics" in message.artifacts:
                self.state.context.epics = message.artifacts["epics"]
            if "stories" in message.artifacts:
                self.state.context.stories = message.artifacts["stories"]

            # Human approval
            self.state.stage = PipelineStage.WORK_ITEMS_APPROVAL
            approval = self.hitl.request_approval(message)
            message.approval_status = approval

            if approval == ApprovalStatus.APPROVED:
                break
            elif approval == ApprovalStatus.REJECTED:
                raise Exception("Work items rejected by user")
            elif approval == ApprovalStatus.REVISION_REQUESTED:
                self._increment_revision("work_items")
                feedback = self.hitl.request_feedback(
                    "What changes would you like to the Epics/Stories?"
                )
                message = await self.business_analyst.refine_work_items(
                    self.state.context, feedback
                )
                self.state.add_message(message)

        self.hitl.notify("Work items approved!", "success")

    @traceable(name="ado_push_stage")
    async def _run_ado_push_stage(self) -> None:
        """Push work items to Azure DevOps."""
        self.state.stage = PipelineStage.ADO_PUSH
        self.hitl.display_progress("Azure DevOps", 3, 6, "Pushing to ADO...")

        if not self.ado_client:
            self.hitl.notify("Azure DevOps client not configured, skipping push", "warning")
            return

        # Confirm before pushing
        if not self.hitl.request_confirmation("Push work items to Azure DevOps?"):
            self.hitl.notify("Azure DevOps push skipped", "info")
            return

        try:
            push_message = await self.business_analyst.push_to_azure_devops(
                self.state.context
            )
            self.state.add_message(push_message)

            if "ado_work_items" in push_message.artifacts:
                self.state.context.ado_work_items = push_message.artifacts["ado_work_items"]

            self.hitl.notify("Work items pushed to Azure DevOps!", "success")
        except Exception as e:
            logger.error(f"Failed to push to ADO: {e}")
            self.hitl.notify(f"ADO push failed: {e}", "warning")

    @traceable(name="architecture_stage")
    async def _run_architecture_stage(self) -> None:
        """Run the architecture design stage."""
        self.state.stage = PipelineStage.ARCHITECTURE
        self.hitl.display_progress("Architecture", 4, 6, "Creating architecture...")

        # Get the work items message from BA
        work_items_message = self.state.get_last_message_from(AgentRole.BUSINESS_ANALYST)
        if not work_items_message:
            raise Exception("No work items message found from Business Analyst")

        while True:
            # Create architecture
            message = await self.architect.create_architecture(
                self.state.context,
                work_items_message,
            )
            self.state.add_message(message)

            # Store architecture in context
            if "architecture" in message.artifacts:
                self.state.context.architecture = message.artifacts["architecture"]

            # Human approval
            self.state.stage = PipelineStage.ARCHITECTURE_APPROVAL
            approval = self.hitl.request_approval(message)
            message.approval_status = approval

            if approval == ApprovalStatus.APPROVED:
                break
            elif approval == ApprovalStatus.REJECTED:
                raise Exception("Architecture rejected by user")
            elif approval == ApprovalStatus.REVISION_REQUESTED:
                self._increment_revision("architecture")
                feedback = self.hitl.request_feedback(
                    "What changes would you like to the architecture?"
                )
                message = await self.architect.refine_architecture(
                    self.state.context, feedback
                )
                self.state.add_message(message)

        self.hitl.notify("Architecture approved!", "success")

    @traceable(name="development_stage")
    async def _run_development_stage(self) -> None:
        """Run the development stage."""
        self.state.stage = PipelineStage.DEVELOPMENT
        self.hitl.display_progress("Development", 5, 6, "Generating code...")

        # Get the architecture message
        architecture_message = self.state.get_last_message_from(AgentRole.ARCHITECT)
        if not architecture_message:
            raise Exception("No architecture message found from Architect")

        while True:
            # Generate code
            message = await self.developer.generate_code(
                self.state.context,
                architecture_message,
            )
            self.state.add_message(message)

            # Store code in context
            if "code" in message.artifacts:
                self.state.context.code_artifacts = message.artifacts["code"]

            # Human approval
            self.state.stage = PipelineStage.DEVELOPMENT_APPROVAL
            approval = self.hitl.request_approval(message)
            message.approval_status = approval

            if approval == ApprovalStatus.APPROVED:
                break
            elif approval == ApprovalStatus.REJECTED:
                raise Exception("Code rejected by user")
            elif approval == ApprovalStatus.REVISION_REQUESTED:
                self._increment_revision("development")
                feedback = self.hitl.request_feedback(
                    "What changes would you like to the code?"
                )
                # Re-generate with feedback
                self.state.context.requirements["revision_feedback"] = feedback
                continue

        self.hitl.notify("Code approved!", "success")

    @traceable(name="github_push_stage")
    async def _run_github_push_stage(self) -> None:
        """Push code to GitHub."""
        self.state.stage = PipelineStage.GITHUB_PUSH
        self.hitl.display_progress("GitHub", 6, 6, "Pushing to GitHub...")

        if not self.github_client:
            self.hitl.notify("GitHub client not configured, skipping push", "warning")
            return

        # Confirm before pushing
        if not self.hitl.request_confirmation("Push code to GitHub and create PR?"):
            self.hitl.notify("GitHub push skipped", "info")
            return

        try:
            # Push code
            repo_name = self.hitl.request_feedback(
                "Enter GitHub repository name (owner/repo):"
            )
            if not repo_name:
                repo_name = f"user/{self.state.context.project_name}"

            push_message = await self.developer.push_to_github(
                self.state.context,
                repo_name=repo_name,
            )
            self.state.add_message(push_message)

            if "github_commits" in push_message.artifacts:
                self.state.context.github_commits = push_message.artifacts["github_commits"]

            # Create PR
            pr_message = await self.developer.create_pull_request(
                self.state.context,
                repo_name=repo_name,
                title=f"feat: {self.state.context.project_name} implementation",
                description=self._generate_pr_description(),
            )
            self.state.add_message(pr_message)

            self.hitl.notify("Code pushed to GitHub with PR created!", "success")
        except Exception as e:
            logger.error(f"Failed to push to GitHub: {e}")
            self.hitl.notify(f"GitHub push failed: {e}", "warning")

    def _increment_revision(self, stage: str) -> None:
        """Increment revision count for a stage."""
        current = self.state.revision_count.get(stage, 0)
        if current >= self.state.max_revisions:
            raise Exception(f"Maximum revisions ({self.state.max_revisions}) exceeded for {stage}")
        self.state.revision_count[stage] = current + 1

    def _generate_pr_description(self) -> str:
        """Generate a PR description from the context."""
        description = f"# {self.state.context.project_name}\n\n"

        if self.state.context.requirements:
            description += "## Requirements\n"
            if "product_vision" in self.state.context.requirements:
                description += f"{self.state.context.requirements['product_vision']}\n\n"

        if self.state.context.epics:
            description += "## Epics\n"
            for epic in self.state.context.epics[:3]:  # Limit to first 3
                description += f"- {epic.get('title', 'Untitled')}\n"
            description += "\n"

        if self.state.context.architecture:
            description += "## Architecture\n"
            arch = self.state.context.architecture
            if "decisions" in arch:
                for decision in arch["decisions"][:3]:
                    description += f"- {decision.get('title', 'Untitled')}\n"
            description += "\n"

        description += "---\n*Generated by SDLC Pipeline with AI Agents*\n"
        return description

    def get_pipeline_summary(self) -> dict[str, Any]:
        """Get a summary of the pipeline execution."""
        return {
            "project_name": self.state.context.project_name,
            "stage": self.state.stage.value,
            "messages_count": len(self.state.messages),
            "errors": self.state.errors,
            "revisions": self.state.revision_count,
            "started_at": self.state.started_at.isoformat(),
            "completed_at": (
                self.state.completed_at.isoformat()
                if self.state.completed_at
                else None
            ),
            "duration_seconds": (
                (self.state.completed_at - self.state.started_at).total_seconds()
                if self.state.completed_at
                else None
            ),
            "has_requirements": bool(self.state.context.requirements),
            "has_epics": bool(self.state.context.epics),
            "has_architecture": bool(self.state.context.architecture),
            "has_code": bool(self.state.context.code_artifacts),
        }


async def run_sdlc_demo():
    """Run a demo of the SDLC pipeline."""
    print("\n" + "=" * 60)
    print("SDLC Multi-Agent Pipeline Demo")
    print("=" * 60 + "\n")

    # Create orchestrator in non-interactive mode for demo
    orchestrator = SDLCPipelineOrchestrator(
        human_in_loop=HumanInTheLoop(interactive=False, auto_approve=True),
    )

    # Run with a sample project idea
    project_idea = """
    Create a task management application with the following features:
    - User authentication and authorization
    - Create, read, update, delete tasks
    - Task categories and tags
    - Due date reminders
    - Team collaboration features
    - Dashboard with task analytics
    """

    state = await orchestrator.run(
        project_idea=project_idea,
        project_name="task-manager-app",
    )

    # Print summary
    summary = orchestrator.get_pipeline_summary()
    print("\n" + "=" * 60)
    print("Pipeline Summary")
    print("=" * 60)
    for key, value in summary.items():
        print(f"  {key}: {value}")

    return state


if __name__ == "__main__":
    asyncio.run(run_sdlc_demo())
