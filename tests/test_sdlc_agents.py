"""Tests for SDLC agents and pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.base_agent import (
    AgentContext,
    AgentMessage,
    AgentRole,
    ApprovalStatus,
)
from src.agents.product_manager_agent import ProductManagerAgent
from src.agents.business_analyst_agent import BusinessAnalystAgent
from src.agents.architect_agent import ArchitectAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.human_in_loop import HumanInTheLoop, InteractionType
from src.agents.sdlc_pipeline import (
    SDLCPipelineOrchestrator,
    PipelineStage,
    PipelineState,
)


class TestAgentRole:
    """Test AgentRole enum."""

    def test_all_roles_defined(self):
        """Test that all required roles are defined."""
        roles = [r.value for r in AgentRole]
        assert "product_manager" in roles
        assert "business_analyst" in roles
        assert "architect" in roles
        assert "developer" in roles
        assert "orchestrator" in roles


class TestApprovalStatus:
    """Test ApprovalStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all approval statuses are defined."""
        statuses = [s.value for s in ApprovalStatus]
        assert "pending" in statuses
        assert "approved" in statuses
        assert "rejected" in statuses
        assert "revision_requested" in statuses


class TestAgentMessage:
    """Test AgentMessage dataclass."""

    def test_message_creation(self):
        """Test creating an agent message."""
        message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Test content",
            artifacts={"key": "value"},
            requires_approval=True,
        )
        assert message.from_agent == AgentRole.PRODUCT_MANAGER
        assert message.to_agent == AgentRole.BUSINESS_ANALYST
        assert message.content == "Test content"
        assert message.artifacts["key"] == "value"
        assert message.requires_approval is True
        assert message.approval_status == ApprovalStatus.PENDING


class TestAgentContext:
    """Test AgentContext dataclass."""

    def test_context_with_project_name(self):
        """Test context with required project_name."""
        context = AgentContext(project_name="test-project")
        assert context.project_name == "test-project"
        assert context.requirements == {}
        assert context.epics == []
        assert context.stories == []
        assert context.architecture == {}
        assert context.code_artifacts == {}
        assert context.ado_work_items == []
        assert context.github_commits == []

    def test_context_with_default_values(self):
        """Test context with default values."""
        context = AgentContext()
        assert context.project_name == ""
        assert context.requirements == {}

    def test_context_with_values(self):
        """Test context with custom values."""
        context = AgentContext(
            project_name="test-project",
            requirements={"feature": "login"},
            epics=[{"id": 1, "title": "Epic 1"}],
        )
        assert context.project_name == "test-project"
        assert context.requirements["feature"] == "login"
        assert len(context.epics) == 1


class TestProductManagerAgent:
    """Test ProductManagerAgent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM with async support."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"product_vision": "Test vision", "requirements": []}'
            )
        )
        return llm

    def test_agent_role(self, mock_llm):
        """Test that agent has correct role."""
        agent = ProductManagerAgent(llm=mock_llm)
        assert agent.role == AgentRole.PRODUCT_MANAGER

    def test_system_prompt(self, mock_llm):
        """Test system prompt is defined."""
        agent = ProductManagerAgent(llm=mock_llm)
        assert "Product Manager" in agent.system_prompt
        assert "requirements" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_requirements(self, mock_llm):
        """Test generating requirements."""
        agent = ProductManagerAgent(llm=mock_llm)
        context = AgentContext(project_name="test-project")

        message = await agent.generate_requirements(context, domain="productivity")

        assert message.from_agent == AgentRole.PRODUCT_MANAGER
        assert message.to_agent == AgentRole.BUSINESS_ANALYST
        assert message.requires_approval is True


class TestBusinessAnalystAgent:
    """Test BusinessAnalystAgent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM with async support."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"epics": [], "stories": []}'
            )
        )
        return llm

    def test_agent_role(self, mock_llm):
        """Test that agent has correct role."""
        agent = BusinessAnalystAgent(llm=mock_llm)
        assert agent.role == AgentRole.BUSINESS_ANALYST

    def test_system_prompt(self, mock_llm):
        """Test system prompt is defined."""
        agent = BusinessAnalystAgent(llm=mock_llm)
        assert "Business Analyst" in agent.system_prompt
        assert "Epic" in agent.system_prompt or "Story" in agent.system_prompt

    @pytest.mark.asyncio
    async def test_create_work_items(self, mock_llm):
        """Test creating work items."""
        agent = BusinessAnalystAgent(llm=mock_llm)
        context = AgentContext(
            project_name="test-project",
            requirements={"product_vision": "Test vision"},
        )
        requirements_message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Requirements",
            artifacts={"requirements": {"vision": "Test vision"}},
        )

        message = await agent.create_work_items(context, requirements_message)

        assert message.from_agent == AgentRole.BUSINESS_ANALYST
        assert message.to_agent == AgentRole.ARCHITECT
        assert message.requires_approval is True


class TestArchitectAgent:
    """Test ArchitectAgent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM with async support."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"c4_context": "", "c4_container": "", "decisions": []}'
            )
        )
        return llm

    def test_agent_role(self, mock_llm):
        """Test that agent has correct role."""
        agent = ArchitectAgent(llm=mock_llm)
        assert agent.role == AgentRole.ARCHITECT

    def test_system_prompt(self, mock_llm):
        """Test system prompt is defined."""
        agent = ArchitectAgent(llm=mock_llm)
        assert "Architect" in agent.system_prompt
        assert "C4" in agent.system_prompt or "Mermaid" in agent.system_prompt

    @pytest.mark.asyncio
    async def test_create_architecture(self, mock_llm):
        """Test creating architecture."""
        agent = ArchitectAgent(llm=mock_llm)
        context = AgentContext(
            project_name="test-project",
            requirements={"product_vision": "Test vision"},
        )
        work_items_message = AgentMessage(
            from_agent=AgentRole.BUSINESS_ANALYST,
            to_agent=AgentRole.ARCHITECT,
            content="Work items",
            artifacts={"work_items": {"epics": [], "stories": []}},
        )

        message = await agent.create_architecture(context, work_items_message)

        assert message.from_agent == AgentRole.ARCHITECT
        assert message.to_agent == AgentRole.DEVELOPER
        assert message.requires_approval is True


class TestDeveloperAgent:
    """Test DeveloperAgent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM with async support."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"project_structure": {}, "files": [], "dependencies": {}}'
            )
        )
        return llm

    def test_agent_role(self, mock_llm):
        """Test that agent has correct role."""
        agent = DeveloperAgent(llm=mock_llm)
        assert agent.role == AgentRole.DEVELOPER

    def test_system_prompt(self, mock_llm):
        """Test system prompt is defined."""
        agent = DeveloperAgent(llm=mock_llm)
        assert "Developer" in agent.system_prompt

    @pytest.mark.asyncio
    async def test_generate_code(self, mock_llm):
        """Test generating code."""
        agent = DeveloperAgent(llm=mock_llm)
        context = AgentContext(
            project_name="test-project",
            architecture={"c4_context": "test"},
        )
        architecture_message = AgentMessage(
            from_agent=AgentRole.ARCHITECT,
            to_agent=AgentRole.DEVELOPER,
            content="Architecture",
            artifacts={"architecture": {"c4_context": "test"}},
        )

        message = await agent.generate_code(context, architecture_message)

        assert message.from_agent == AgentRole.DEVELOPER
        # Developer is the last agent in the pipeline, so to_agent is None
        assert message.to_agent is None
        assert message.requires_approval is True


class TestHumanInTheLoop:
    """Test HumanInTheLoop handler."""

    def test_auto_approve_mode(self):
        """Test auto-approve mode."""
        hitl = HumanInTheLoop(auto_approve=True)
        message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Test",
        )
        status = hitl.request_approval(message)
        assert status == ApprovalStatus.APPROVED

    def test_non_interactive_mode(self):
        """Test non-interactive mode."""
        hitl = HumanInTheLoop(interactive=False)
        message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Test",
        )
        status = hitl.request_approval(message)
        assert status == ApprovalStatus.APPROVED

    def test_register_callback(self):
        """Test registering a callback."""
        hitl = HumanInTheLoop()

        def my_callback(interaction):
            return ApprovalStatus.APPROVED

        hitl.register_callback(InteractionType.APPROVAL, my_callback)
        assert InteractionType.APPROVAL in hitl._interaction_callbacks

    def test_request_confirmation_auto_approve(self):
        """Test confirmation with auto-approve."""
        hitl = HumanInTheLoop(auto_approve=True)
        result = hitl.request_confirmation("Continue?")
        assert result is True

    def test_notify(self):
        """Test notification."""
        hitl = HumanInTheLoop(interactive=False)
        # Should not raise
        hitl.notify("Test message", "info")
        hitl.notify("Warning", "warning")
        hitl.notify("Error", "error")


class TestPipelineState:
    """Test PipelineState dataclass."""

    def test_initial_state(self):
        """Test initial pipeline state."""
        state = PipelineState()
        assert state.stage == PipelineStage.INITIALIZATION
        assert len(state.messages) == 0
        assert len(state.errors) == 0
        assert state.completed_at is None

    def test_add_message(self):
        """Test adding a message to state."""
        state = PipelineState()
        message = AgentMessage(
            from_agent=AgentRole.PRODUCT_MANAGER,
            to_agent=AgentRole.BUSINESS_ANALYST,
            content="Test",
        )
        state.add_message(message)
        assert len(state.messages) == 1

    def test_get_last_message_from(self):
        """Test getting last message from agent."""
        state = PipelineState()

        # Add multiple messages
        state.add_message(
            AgentMessage(
                from_agent=AgentRole.PRODUCT_MANAGER,
                to_agent=AgentRole.BUSINESS_ANALYST,
                content="First PM message",
            )
        )
        state.add_message(
            AgentMessage(
                from_agent=AgentRole.BUSINESS_ANALYST,
                to_agent=AgentRole.ARCHITECT,
                content="BA message",
            )
        )
        state.add_message(
            AgentMessage(
                from_agent=AgentRole.PRODUCT_MANAGER,
                to_agent=AgentRole.BUSINESS_ANALYST,
                content="Second PM message",
            )
        )

        last_pm = state.get_last_message_from(AgentRole.PRODUCT_MANAGER)
        assert last_pm is not None
        assert last_pm.content == "Second PM message"

        last_dev = state.get_last_message_from(AgentRole.DEVELOPER)
        assert last_dev is None


class TestSDLCPipelineOrchestrator:
    """Test SDLCPipelineOrchestrator."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.invoke = MagicMock(
            return_value=MagicMock(
                content='{"product_vision": "Test", "requirements": [], "epics": [], "stories": [], "c4_context": "", "project_structure": {}}'
            )
        )
        return llm

    def test_orchestrator_creation(self, mock_llm):
        """Test creating orchestrator."""
        hitl = HumanInTheLoop(auto_approve=True)
        orchestrator = SDLCPipelineOrchestrator(llm=mock_llm, human_in_loop=hitl)

        assert orchestrator.product_manager is not None
        assert orchestrator.business_analyst is not None
        assert orchestrator.architect is not None
        assert orchestrator.developer is not None

    def test_get_pipeline_summary(self, mock_llm):
        """Test getting pipeline summary."""
        hitl = HumanInTheLoop(auto_approve=True)
        orchestrator = SDLCPipelineOrchestrator(llm=mock_llm, human_in_loop=hitl)

        summary = orchestrator.get_pipeline_summary()

        assert "project_name" in summary
        assert "stage" in summary
        assert "messages_count" in summary
        assert "started_at" in summary

    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, mock_llm):
        """Test pipeline initialization."""
        hitl = HumanInTheLoop(auto_approve=True, interactive=False)
        orchestrator = SDLCPipelineOrchestrator(
            llm=mock_llm,
            human_in_loop=hitl,
        )

        # Run with a simple project idea
        with patch.object(
            orchestrator.product_manager,
            "generate_requirements",
            new_callable=AsyncMock,
        ) as mock_pm:
            mock_pm.return_value = AgentMessage(
                from_agent=AgentRole.PRODUCT_MANAGER,
                to_agent=AgentRole.BUSINESS_ANALYST,
                content="Requirements generated",
                artifacts={"requirements": {"vision": "Test"}},
            )

            with patch.object(
                orchestrator.business_analyst,
                "create_work_items",
                new_callable=AsyncMock,
            ) as mock_ba:
                mock_ba.return_value = AgentMessage(
                    from_agent=AgentRole.BUSINESS_ANALYST,
                    to_agent=AgentRole.ARCHITECT,
                    content="Work items created",
                    artifacts={"epics": [], "stories": []},
                )

                with patch.object(
                    orchestrator.architect,
                    "create_architecture",
                    new_callable=AsyncMock,
                ) as mock_arch:
                    mock_arch.return_value = AgentMessage(
                        from_agent=AgentRole.ARCHITECT,
                        to_agent=AgentRole.DEVELOPER,
                        content="Architecture created",
                        artifacts={"architecture": {}},
                    )

                    with patch.object(
                        orchestrator.developer,
                        "generate_code",
                        new_callable=AsyncMock,
                    ) as mock_dev:
                        mock_dev.return_value = AgentMessage(
                            from_agent=AgentRole.DEVELOPER,
                            to_agent=AgentRole.ORCHESTRATOR,
                            content="Code generated",
                            artifacts={"code": {}},
                        )

                        state = await orchestrator.run(
                            project_idea="Build a test app",
                            project_name="test-app",
                        )

                        assert state.stage == PipelineStage.COMPLETED
                        assert len(state.errors) == 0


class TestPipelineStages:
    """Test PipelineStage enum."""

    def test_all_stages_defined(self):
        """Test that all pipeline stages are defined."""
        stages = [s.value for s in PipelineStage]

        expected_stages = [
            "initialization",
            "requirements",
            "requirements_approval",
            "work_items",
            "work_items_approval",
            "ado_push",
            "architecture",
            "architecture_approval",
            "development",
            "development_approval",
            "github_push",
            "completed",
            "failed",
        ]

        for stage in expected_stages:
            assert stage in stages
