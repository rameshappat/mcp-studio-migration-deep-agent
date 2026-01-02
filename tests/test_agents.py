"""Tests for the agents module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.orchestrator import AgentOrchestrator


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    def test_init(self):
        """Test orchestrator initialization."""
        orchestrator = AgentOrchestrator()
        assert orchestrator._agents == {}
        assert orchestrator._default_agent is None

    def test_register_agent(self):
        """Test registering an agent."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        
        orchestrator.register_agent("test", mock_agent)
        
        assert "test" in orchestrator._agents
        assert orchestrator._default_agent == "test"

    def test_register_default_agent(self):
        """Test registering a default agent."""
        orchestrator = AgentOrchestrator()
        mock_agent1 = MagicMock()
        mock_agent2 = MagicMock()
        
        orchestrator.register_agent("first", mock_agent1)
        orchestrator.register_agent("second", mock_agent2, default=True)
        
        assert orchestrator._default_agent == "second"

    def test_get_agent_by_name(self):
        """Test getting an agent by name."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        orchestrator.register_agent("test", mock_agent)
        
        result = orchestrator.get_agent("test")
        assert result is mock_agent

    def test_get_default_agent(self):
        """Test getting the default agent."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        orchestrator.register_agent("test", mock_agent)
        
        result = orchestrator.get_agent()  # No name = default
        assert result is mock_agent

    def test_get_nonexistent_agent(self):
        """Test getting an agent that doesn't exist."""
        orchestrator = AgentOrchestrator()
        result = orchestrator.get_agent("nonexistent")
        assert result is None

    def test_list_agents(self):
        """Test listing registered agents."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent("agent1", MagicMock())
        orchestrator.register_agent("agent2", MagicMock())
        
        agents = orchestrator.list_agents()
        assert set(agents) == {"agent1", "agent2"}

    @pytest.mark.asyncio
    async def test_route_request(self):
        """Test routing a request to an agent."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Test response")
        orchestrator.register_agent("test", mock_agent)
        
        result = await orchestrator.route_request("Hello")
        
        assert result == "Test response"
        mock_agent.run.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_route_request_agent_not_found(self):
        """Test routing to a non-existent agent."""
        orchestrator = AgentOrchestrator()
        
        result = await orchestrator.route_request("Hello", "nonexistent")
        
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_execute_workflow(self):
        """Test executing a multi-step workflow."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=["Result 1", "Result 2"])
        orchestrator.register_agent("test", mock_agent)
        
        steps = [
            {"name": "step1", "agent": "test", "message": "First task"},
            {"name": "step2", "agent": "test", "message": "Second task with {step1}"},
        ]
        
        results = await orchestrator.execute_workflow(steps)
        
        assert len(results) == 2
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_parallel_execute(self):
        """Test parallel execution of requests."""
        orchestrator = AgentOrchestrator()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=["Response 1", "Response 2"])
        orchestrator.register_agent("test", mock_agent)
        
        requests = [
            {"agent": "test", "message": "Request 1"},
            {"agent": "test", "message": "Request 2"},
        ]
        
        results = await orchestrator.parallel_execute(requests)
        
        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)
