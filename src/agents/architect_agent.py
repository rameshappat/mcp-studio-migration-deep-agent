"""Architect Agent - Creates architecture and design artifacts."""

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


class ArchitectAgent(BaseAgent):
    """Agent that acts as a Software Architect, creating design artifacts."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.5,
    ):
        """Initialize the Architect Agent."""
        super().__init__(
            role=AgentRole.ARCHITECT,
            llm=llm,
            model_name=model_name,
            temperature=temperature,
        )

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for the Architect."""
        return """You are an experienced Software Architect with expertise in 
designing scalable, maintainable systems using modern technologies.

Your responsibilities:
1. Analyze requirements and create system architecture
2. Design component diagrams using C4 model
3. Create sequence diagrams for key flows
4. Define API contracts and data models
5. Select appropriate technology stack
6. Document architectural decisions (ADRs)

When creating architecture, structure your output as JSON:
{
    "architecture_overview": "High-level description",
    "technology_stack": {
        "frontend": ["React", "TypeScript"],
        "backend": ["Python", "FastAPI"],
        "database": ["PostgreSQL"],
        "infrastructure": ["Docker", "Kubernetes"]
    },
    "components": [
        {
            "name": "Component name",
            "type": "service|frontend|database|external",
            "description": "Component description",
            "responsibilities": ["Resp 1", "Resp 2"],
            "technologies": ["Tech 1", "Tech 2"],
            "apis": [
                {
                    "endpoint": "/api/resource",
                    "method": "GET|POST|PUT|DELETE",
                    "description": "API description"
                }
            ]
        }
    ],
    "diagrams": {
        "c4_context": "Mermaid diagram code",
        "c4_container": "Mermaid diagram code",
        "c4_component": "Mermaid diagram code",
        "sequence_diagrams": {
            "flow_name": "Mermaid sequence diagram"
        }
    },
    "data_models": [
        {
            "name": "EntityName",
            "fields": [
                {"name": "id", "type": "uuid", "required": true},
                {"name": "name", "type": "string", "required": true}
            ],
            "relationships": ["Entity2"]
        }
    ],
    "adrs": [
        {
            "id": "ADR-001",
            "title": "Decision title",
            "status": "proposed|accepted|deprecated",
            "context": "Why this decision is needed",
            "decision": "What was decided",
            "consequences": "Impact of the decision"
        }
    ],
    "non_functional_requirements": {
        "scalability": "Description",
        "security": "Description",
        "performance": "Description"
    }
}

Use Mermaid syntax for all diagrams.
Follow C4 model for architecture diagrams.
Consider security, scalability, and maintainability in all decisions."""

    async def _process_response(
        self, response: AIMessage, context: AgentContext
    ) -> AgentMessage:
        """Process the LLM response into architecture artifacts."""
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

            architecture = json.loads(json_str)
            artifacts["architecture"] = architecture

            # Update context
            context.architecture = architecture

            # Extract diagrams for easier access
            if "diagrams" in architecture:
                artifacts["diagrams"] = architecture["diagrams"]

        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Could not parse structured output: {e}")
            artifacts["raw_architecture"] = content
            
            # Try to extract Mermaid diagrams even if JSON fails
            artifacts["diagrams"] = self._extract_mermaid_diagrams(content)

        return AgentMessage(
            from_agent=self.role,
            to_agent=AgentRole.DEVELOPER,
            content=content,
            artifacts=artifacts,
            requires_approval=True,
            approval_status=ApprovalStatus.PENDING,
            metadata={"stage": "architecture_design"},
        )

    def _extract_mermaid_diagrams(self, content: str) -> dict[str, str]:
        """Extract Mermaid diagrams from content."""
        diagrams = {}
        
        # Find all mermaid code blocks
        if "```mermaid" in content:
            parts = content.split("```mermaid")
            for i, part in enumerate(parts[1:], 1):
                if "```" in part:
                    diagram = part.split("```")[0].strip()
                    diagrams[f"diagram_{i}"] = diagram
        
        return diagrams

    async def create_architecture(
        self,
        context: AgentContext,
        work_items_message: AgentMessage,
    ) -> AgentMessage:
        """Create architecture based on requirements and stories.

        Args:
            context: The shared workflow context.
            work_items_message: Message from Business Analyst with work items.

        Returns:
            Agent message with architecture artifacts.
        """
        work_items = work_items_message.artifacts.get("work_items", {})

        input_message = AgentMessage(
            from_agent=AgentRole.BUSINESS_ANALYST,
            to_agent=self.role,
            content=f"""Based on the following requirements and user stories, create a 
comprehensive software architecture.

Project: {context.project_name}
Description: {context.project_description}

Requirements:
{json.dumps(context.requirements, indent=2)}

Epics:
{json.dumps(context.epics, indent=2)}

Stories:
{json.dumps(context.stories, indent=2)}

Create:
1. C4 diagrams (Context, Container, Component) in Mermaid format
2. Sequence diagrams for key user flows
3. Data models
4. API specifications
5. Technology stack recommendations
6. Architectural Decision Records (ADRs)

Ensure the architecture supports all functional and non-functional requirements.""",
        )

        return await self.process(input_message, context)

    async def generate_c4_diagrams(self, context: AgentContext) -> dict[str, str]:
        """Generate C4 model diagrams for the architecture.

        Args:
            context: The shared workflow context.

        Returns:
            Dictionary of diagram type to Mermaid code.
        """
        diagrams = {}

        # Generate Context diagram
        context_diagram = f"""
graph TB
    subgraph boundary [System Boundary]
        system["{context.project_name}<br/>Software System"]
    end
    
    user((User))
    user --> system
    
    style system fill:#438DD5,stroke:#333,color:#fff
    style user fill:#08427B,stroke:#333,color:#fff
"""
        diagrams["c4_context"] = context_diagram

        # Generate Container diagram based on architecture
        if context.architecture and "components" in context.architecture:
            components = context.architecture["components"]
            container_parts = ["graph TB"]
            
            for i, comp in enumerate(components):
                comp_id = f"comp{i}"
                comp_name = comp.get("name", f"Component {i}")
                comp_type = comp.get("type", "service")
                container_parts.append(f'    {comp_id}["{comp_name}<br/>{comp_type}"]')
            
            diagrams["c4_container"] = "\n".join(container_parts)

        return diagrams

    async def refine_architecture(
        self,
        context: AgentContext,
        feedback: str,
    ) -> AgentMessage:
        """Refine architecture based on feedback.

        Args:
            context: The shared workflow context.
            feedback: Feedback from human or other agents.

        Returns:
            Agent message with refined architecture.
        """
        context.human_feedback.append(feedback)

        input_message = AgentMessage(
            from_agent=AgentRole.ORCHESTRATOR,
            to_agent=self.role,
            content=f"""Refine the architecture based on the following feedback:

Feedback: {feedback}

Current Architecture:
{json.dumps(context.architecture, indent=2)}

Provide updated architecture addressing the feedback.""",
        )

        return await self.process(input_message, context)
