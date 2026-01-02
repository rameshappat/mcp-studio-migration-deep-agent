"""Business Analyst Agent - Creates Epics and User Stories for Azure DevOps."""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from .base_agent import (
    AgentContext,
    AgentMessage,
    AgentRole,
    ApprovalStatus,
    BaseAgent,
)

logger = logging.getLogger(__name__)


class BusinessAnalystAgent(BaseAgent):
    """Agent that acts as a Business Analyst/Product Owner, creating Epics and Stories."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.6,
        ado_client: Any = None,
    ):
        """Initialize the Business Analyst Agent."""
        super().__init__(
            role=AgentRole.BUSINESS_ANALYST,
            llm=llm,
            model_name=model_name,
            temperature=temperature,
        )
        self._ado_client = ado_client

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for the Business Analyst."""
        return """You are an experienced Business Analyst and Product Owner with expertise 
in Agile methodologies and Azure DevOps.

Your responsibilities:
1. Break down high-level requirements into Epics
2. Create detailed User Stories with acceptance criteria
3. Estimate story points using Fibonacci sequence
4. Define clear Definition of Done
5. Organize work items for Azure DevOps Boards

When creating work items, structure your output as JSON:
{
    "epics": [
        {
            "id": "EPIC-001",
            "title": "Epic title",
            "description": "Epic description",
            "business_value": "Value statement",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "stories": ["STORY-001", "STORY-002"]
        }
    ],
    "stories": [
        {
            "id": "STORY-001",
            "epic_id": "EPIC-001",
            "title": "As a [user], I want [feature] so that [benefit]",
            "description": "Detailed description",
            "acceptance_criteria": [
                "Given [context], When [action], Then [result]"
            ],
            "story_points": 5,
            "priority": 1,
            "tags": ["frontend", "api"]
        }
    ],
    "tasks": [
        {
            "id": "TASK-001",
            "story_id": "STORY-001",
            "title": "Task title",
            "description": "Task description",
            "estimated_hours": 4
        }
    ]
}

Use the Gherkin format (Given-When-Then) for acceptance criteria.
Ensure stories are small enough to complete in a single sprint.
Consider technical dependencies when organizing work."""

    def set_ado_client(self, ado_client: Any) -> None:
        """Set the Azure DevOps MCP client."""
        self._ado_client = ado_client

    async def _process_response(
        self, response: AIMessage, context: AgentContext
    ) -> AgentMessage:
        """Process the LLM response into Epics and Stories."""
        content = str(response.content)

        artifacts = {}
        try:
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            work_items = json.loads(json_str)
            artifacts["work_items"] = work_items

            # Update context
            if "epics" in work_items:
                context.epics = work_items["epics"]
            if "stories" in work_items:
                context.stories = work_items["stories"]

        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Could not parse structured output: {e}")
            artifacts["raw_work_items"] = content

        return AgentMessage(
            from_agent=self.role,
            to_agent=AgentRole.ARCHITECT,
            content=content,
            artifacts=artifacts,
            requires_approval=True,
            approval_status=ApprovalStatus.PENDING,
            metadata={"stage": "work_item_creation"},
        )

    async def create_work_items(
        self,
        context: AgentContext,
        requirements_message: AgentMessage,
    ) -> AgentMessage:
        """Create Epics and Stories from requirements.

        Args:
            context: The shared workflow context.
            requirements_message: Message from Product Manager with requirements.

        Returns:
            Agent message with created work items.
        """
        requirements = requirements_message.artifacts.get("requirements", {})

        input_message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=self.role,
            content=f"""Based on the following requirements, create Epics and User Stories 
for Azure DevOps Boards.

Requirements:
{json.dumps(requirements, indent=2)}

Create detailed work items following Agile best practices.
Ensure proper hierarchy: Epic -> Story -> Task
Include acceptance criteria in Gherkin format.""",
        )

        return await self.process(input_message, context)

    async def push_to_azure_devops(
        self,
        context: AgentContext,
    ) -> dict[str, Any]:
        """Push work items to Azure DevOps using MCP.

        Args:
            context: The shared workflow context.

        Returns:
            Dictionary with created work item IDs.
        """
        if not self._ado_client:
            logger.warning("Azure DevOps client not configured")
            return {"error": "ADO client not configured"}

        created_items = {"epics": [], "stories": [], "tasks": []}
        project = self._ado_client.project

        try:
            # Create Epics using correct tool name and parameter format
            for epic in context.epics:
                fields = [
                    {"name": "System.Title", "value": epic["title"]},
                    {"name": "System.Description", "value": epic.get("description", ""), "format": "Html"},
                ]
                if epic.get("tags"):
                    fields.append({"name": "System.Tags", "value": ",".join(epic.get("tags", []))})
                
                result = await self._ado_client.call_tool(
                    "wit_create_work_item",
                    {
                        "project": project,
                        "workItemType": "Epic",
                        "fields": fields,
                    },
                )
                created_items["epics"].append({
                    "local_id": epic["id"],
                    "ado_id": result.get("id") if isinstance(result, dict) else None,
                    "result": result,
                })
                logger.info(f"Created Epic: {epic['title']} - Result: {result}")

            # Create Stories using correct tool name and parameter format
            # Note: Azure DevOps Basic process uses "Issue" instead of "User Story"
            # Agile process uses "User Story", Scrum uses "Product Backlog Item"
            story_type = "Issue"  # Basic process template
            for story in context.stories:
                acceptance_criteria = "\n".join(
                    f"- {ac}" for ac in story.get("acceptance_criteria", [])
                )
                description = f"{story.get('description', '')}\n\n<b>Acceptance Criteria:</b>\n{acceptance_criteria}"
                
                fields = [
                    {"name": "System.Title", "value": story["title"]},
                    {"name": "System.Description", "value": description, "format": "Html"},
                ]
                # Story points - Effort field for Basic process
                if story.get("story_points"):
                    fields.append({"name": "Microsoft.VSTS.Scheduling.Effort", "value": str(story.get("story_points", 0))})
                
                result = await self._ado_client.call_tool(
                    "wit_create_work_item",
                    {
                        "project": project,
                        "workItemType": story_type,
                        "fields": fields,
                    },
                )
                created_items["stories"].append({
                    "local_id": story["id"],
                    "ado_id": result.get("id") if isinstance(result, dict) else None,
                    "result": result,
                })
                logger.info(f"Created Story: {story['title']} - Result: {result}")

            context.ado_work_items = created_items
            return created_items

        except Exception as e:
            logger.error(f"Error pushing to Azure DevOps: {e}")
            return {"error": str(e)}

    async def refine_work_items(
        self,
        context: AgentContext,
        feedback: str,
    ) -> AgentMessage:
        """Refine work items based on feedback.

        Args:
            context: The shared workflow context.
            feedback: Feedback from human or other agents.

        Returns:
            Agent message with refined work items.
        """
        context.human_feedback.append(feedback)

        input_message = AgentMessage(
            from_agent=AgentRole.ORCHESTRATOR,
            to_agent=self.role,
            content=f"""Refine the work items based on the following feedback:

Feedback: {feedback}

Current Epics: {json.dumps(context.epics, indent=2)}
Current Stories: {json.dumps(context.stories, indent=2)}

Provide updated work items addressing the feedback.""",
        )

        return await self.process(input_message, context)
