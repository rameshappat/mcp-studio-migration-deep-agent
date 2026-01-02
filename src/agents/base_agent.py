"""Base agent class for all specialized agents."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles for different agents in the pipeline."""

    PRODUCT_MANAGER = "product_manager"
    BUSINESS_ANALYST = "business_analyst"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    ORCHESTRATOR = "orchestrator"


class ApprovalStatus(Enum):
    """Status of human approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


@dataclass
class AgentMessage:
    """Message passed between agents."""

    from_agent: AgentRole
    to_agent: AgentRole | None
    content: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Shared context across agents in a workflow."""

    project_name: str = ""
    project_description: str = ""
    requirements: dict[str, Any] = field(default_factory=dict)
    epics: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    architecture: dict[str, Any] = field(default_factory=dict)
    code_artifacts: dict[str, str] = field(default_factory=dict)
    ado_work_items: list[dict[str, Any]] = field(default_factory=list)
    github_commits: list[dict[str, Any]] = field(default_factory=list)
    conversation_history: list[AgentMessage] = field(default_factory=list)
    human_feedback: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        role: AgentRole,
        llm: ChatOpenAI | None = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
    ):
        """Initialize the base agent.

        Args:
            role: The role of this agent.
            llm: Optional pre-configured LLM instance.
            model_name: OpenAI model to use (if llm not provided).
            temperature: Temperature for LLM responses (if llm not provided).
        """
        self.role = role
        self.model_name = model_name
        self.temperature = temperature
        self._llm = llm if llm is not None else ChatOpenAI(model=model_name, temperature=temperature)
        self._tools: list[Any] = []
        self._human_approval_callback: Callable[[AgentMessage], ApprovalStatus] | None = None

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    def set_tools(self, tools: list[Any]) -> None:
        """Set the tools available to this agent."""
        self._tools = tools
        if tools:
            self._llm = self._llm.bind_tools(tools)

    def set_human_approval_callback(
        self, callback: Callable[[AgentMessage], ApprovalStatus]
    ) -> None:
        """Set the callback for human approval."""
        self._human_approval_callback = callback

    @traceable(name="agent.process")
    async def process(
        self,
        input_message: AgentMessage,
        context: AgentContext,
    ) -> AgentMessage:
        """Process an incoming message and return a response.

        Args:
            input_message: The incoming message from another agent or human.
            context: The shared workflow context.

        Returns:
            Response message with artifacts.
        """
        logger.info(f"{self.role.value} processing message from {input_message.from_agent.value}")

        # Build messages for the LLM
        messages = self._build_messages(input_message, context)

        # Generate response
        response = await self._llm.ainvoke(messages)

        # Process the response into an agent message
        output = await self._process_response(response, context)

        # Check if human approval is needed
        if output.requires_approval and self._human_approval_callback:
            output.approval_status = self._human_approval_callback(output)

            if output.approval_status == ApprovalStatus.REJECTED:
                logger.info(f"{self.role.value} output rejected by human")
            elif output.approval_status == ApprovalStatus.REVISION_REQUESTED:
                logger.info(f"{self.role.value} revision requested by human")

        # Add to conversation history
        context.conversation_history.append(input_message)
        context.conversation_history.append(output)

        return output

    def _build_messages(
        self, input_message: AgentMessage, context: AgentContext
    ) -> list[BaseMessage]:
        """Build the message list for the LLM."""
        messages: list[BaseMessage] = [
            SystemMessage(content=self.system_prompt),
        ]

        # Add context summary
        context_summary = self._build_context_summary(context)
        if context_summary:
            messages.append(SystemMessage(content=f"Current Project Context:\n{context_summary}"))

        # Add recent conversation history
        for msg in context.conversation_history[-5:]:
            if msg.from_agent == self.role:
                messages.append(AIMessage(content=msg.content))
            else:
                messages.append(HumanMessage(content=f"[{msg.from_agent.value}]: {msg.content}"))

        # Add the current input
        messages.append(HumanMessage(content=input_message.content))

        return messages

    def _build_context_summary(self, context: AgentContext) -> str:
        """Build a summary of the current context."""
        parts = [f"Project: {context.project_name}"]

        if context.project_description:
            parts.append(f"Description: {context.project_description}")

        if context.requirements:
            parts.append(f"Requirements: {len(context.requirements)} defined")

        if context.epics:
            parts.append(f"Epics: {len(context.epics)} created")

        if context.stories:
            parts.append(f"Stories: {len(context.stories)} created")

        if context.architecture:
            parts.append("Architecture: Defined")

        if context.code_artifacts:
            parts.append(f"Code Files: {len(context.code_artifacts)} generated")

        return "\n".join(parts)

    @abstractmethod
    async def _process_response(
        self, response: AIMessage, context: AgentContext
    ) -> AgentMessage:
        """Process the LLM response into an agent message.

        Args:
            response: The LLM response.
            context: The shared workflow context.

        Returns:
            Processed agent message with artifacts.
        """
        pass

    async def handoff_to(
        self,
        target_agent: "BaseAgent",
        message: AgentMessage,
        context: AgentContext,
    ) -> AgentMessage:
        """Hand off work to another agent.

        Args:
            target_agent: The agent to hand off to.
            message: The message to send.
            context: The shared workflow context.

        Returns:
            Response from the target agent.
        """
        logger.info(f"{self.role.value} handing off to {target_agent.role.value}")

        # Update message routing
        message.from_agent = self.role
        message.to_agent = target_agent.role

        return await target_agent.process(message, context)
