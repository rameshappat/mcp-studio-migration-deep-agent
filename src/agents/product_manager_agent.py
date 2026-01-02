"""Product Manager Agent - Generates business requirements and product ideas."""

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


class ProductManagerAgent(BaseAgent):
    """Agent that acts as a Product Manager, generating business requirements."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.8,
    ):
        """Initialize the Product Manager Agent."""
        super().__init__(
            role=AgentRole.PRODUCT_MANAGER,
            llm=llm,
            model_name=model_name,
            temperature=temperature,
        )

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for the Product Manager."""
        return """You are an experienced Product Manager with expertise in identifying 
market opportunities and defining product requirements.

Your responsibilities:
1. Generate innovative business requirement ideas based on market trends
2. Define clear product vision and goals
3. Identify target users and their pain points
4. Create high-level feature requirements
5. Prioritize features based on business value

When generating requirements, structure your output as JSON with:
{
    "product_vision": "Clear vision statement",
    "target_users": ["User persona 1", "User persona 2"],
    "pain_points": ["Pain point 1", "Pain point 2"],
    "requirements": [
        {
            "id": "REQ-001",
            "title": "Requirement title",
            "description": "Detailed description",
            "priority": "high|medium|low",
            "business_value": "Value statement"
        }
    ],
    "success_metrics": ["Metric 1", "Metric 2"]
}

Be creative but practical. Focus on solving real user problems.
Always consider technical feasibility and market timing."""

    async def _process_response(
        self, response: AIMessage, context: AgentContext
    ) -> AgentMessage:
        """Process the LLM response into requirements."""
        content = str(response.content)

        # Try to parse structured output
        artifacts = {}
        try:
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            requirements_data = json.loads(json_str)
            artifacts["requirements"] = requirements_data

            # Update context
            if "requirements" in requirements_data:
                context.requirements = requirements_data["requirements"]
            if "product_vision" in requirements_data:
                context.project_description = requirements_data["product_vision"]

        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Could not parse structured output: {e}")
            artifacts["raw_requirements"] = content

        return AgentMessage(
            from_agent=self.role,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content=content,
            artifacts=artifacts,
            requires_approval=True,  # Requires human approval before proceeding
            approval_status=ApprovalStatus.PENDING,
            metadata={"stage": "requirements_generation"},
        )

    async def generate_requirements(
        self,
        context: AgentContext,
        domain: str | None = None,
        constraints: list[str] | None = None,
    ) -> AgentMessage:
        """Generate new business requirements.

        Args:
            context: The shared workflow context.
            domain: Optional domain focus (e.g., "fintech", "healthcare").
            constraints: Optional list of constraints to consider.

        Returns:
            Agent message with generated requirements.
        """
        prompt_parts = [
            f"Generate business requirements for a new product in the project: {context.project_name}."
        ]

        if domain:
            prompt_parts.append(f"Focus on the {domain} domain.")

        if constraints:
            prompt_parts.append(f"Consider these constraints: {', '.join(constraints)}")

        prompt_parts.append("Provide comprehensive requirements in the structured JSON format.")

        input_message = AgentMessage(
            from_agent=AgentRole.ORCHESTRATOR,
            to_agent=self.role,
            content=" ".join(prompt_parts),
        )

        return await self.process(input_message, context)

    async def refine_requirements(
        self,
        context: AgentContext,
        feedback: str,
    ) -> AgentMessage:
        """Refine requirements based on feedback.

        Args:
            context: The shared workflow context.
            feedback: Feedback from human or other agents.

        Returns:
            Agent message with refined requirements.
        """
        context.human_feedback.append(feedback)

        input_message = AgentMessage(
            from_agent=AgentRole.ORCHESTRATOR,
            to_agent=self.role,
            content=f"""Based on the following feedback, refine the requirements:

Feedback: {feedback}

Current requirements: {json.dumps(context.requirements, indent=2)}

Provide updated requirements addressing the feedback.""",
        )

        return await self.process(input_message, context)
