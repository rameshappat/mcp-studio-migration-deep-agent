"""Tests for Deep Agent implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.tools import tool

from src.agents.deep_agent import (
    DeepAgent,
    AgentDecisionType,
    ConfidenceLevel,
    ValidationResult,
    SubAgentSpec,
)


# ============================================================================
# Test Tools
# ============================================================================

@tool
def test_tool_simple() -> str:
    """A simple test tool that returns success."""
    return "success"


@tool
def test_tool_with_args(message: str) -> str:
    """A test tool that echoes the message."""
    return f"Echo: {message}"


@tool
async def test_tool_async() -> str:
    """An async test tool."""
    await asyncio.sleep(0.1)
    return "async_success"


@tool
def test_tool_error() -> str:
    """A tool that raises an error."""
    raise ValueError("Intentional error for testing")


# ============================================================================
# Test DeepAgent Creation
# ============================================================================

def test_deep_agent_creation():
    """Test creating a deep agent."""
    # Mock LLM to avoid needing API key
    mock_llm = MagicMock()
    
    agent = DeepAgent(
        role="Test Agent",
        objective="Test objective",
        tools=[test_tool_simple],
        model_name="gpt-4-turbo",
        temperature=0.7,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    assert agent.role == "Test Agent"
    assert agent.objective == "Test objective"
    assert len(agent.tools) == 1
    assert agent.iteration_count == 0
    assert agent.enable_self_correction is True
    assert agent.enable_agent_spawning is True


def test_deep_agent_with_configuration():
    """Test agent with custom configuration."""
    agent = DeepAgent(
        role="Custom Agent",
        objective="Custom objective",
        tools=[],
        min_confidence_for_autonomy=ConfidenceLevel.HIGH,
        enable_self_correction=False,
        enable_agent_spawning=False,
        max_iterations=5,
    )
    
    assert agent.min_confidence_for_autonomy == ConfidenceLevel.HIGH
    assert agent.enable_self_correction is False
    assert agent.enable_agent_spawning is False
    assert agent.max_iterations == 5


# ============================================================================
# Test Agent Execution
# ============================================================================

@pytest.mark.asyncio
async def test_agent_simple_execution():
    """Test basic agent execution."""
    
    # Mock LLM to return a complete response
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Task completed successfully"
    mock_response.tool_calls = None
    mock_llm.ainvoke.return_value = mock_response
    
    agent = DeepAgent(
        role="Test Agent",
        objective="Complete a simple task",
        tools=[],
        max_iterations=3,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    # Mock decision making to return COMPLETE
    with patch.object(agent, '_make_decision') as mock_decision:
        mock_decision.return_value = MagicMock(
            decision_type=AgentDecisionType.COMPLETE,
            reasoning="Task is done",
            confidence=ConfidenceLevel.HIGH,
            next_action="",
            metadata={},
        )
        
        result = await agent.execute("Test task", {})
        
        assert result["status"] == "completed"
        assert "Task completed successfully" in result["output"]
        assert agent.iteration_count == 1


@pytest.mark.asyncio
async def test_agent_with_tool_calls():
    """Test agent that uses tools."""
    
    # Mock LLM to first call tools, then complete
    mock_llm = AsyncMock()
    
    # First response: tool call
    tool_call_response = MagicMock()
    tool_call_response.content = ""
    tool_call_response.tool_calls = [
        {
            "id": "call_1",
            "name": "test_tool_simple",
            "args": {},
        }
    ]
    
    # Second response: completion
    complete_response = MagicMock()
    complete_response.content = "Used tool successfully"
    complete_response.tool_calls = None
    
    mock_llm.ainvoke.side_effect = [tool_call_response, complete_response]
    
    agent = DeepAgent(
        role="Tool User",
        objective="Use tools",
        tools=[test_tool_simple],
        max_iterations=5,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    # Mock decision
    with patch.object(agent, '_make_decision') as mock_decision:
        mock_decision.return_value = MagicMock(
            decision_type=AgentDecisionType.COMPLETE,
            reasoning="Done",
            confidence=ConfidenceLevel.HIGH,
            next_action="",
            metadata={},
        )
        
        result = await agent.execute("Use tool", {})
        
        assert result["status"] == "completed"
        assert agent.iteration_count == 2  # One for tool call, one for completion


@pytest.mark.asyncio
async def test_agent_max_iterations():
    """Test agent respects max iterations."""
    
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Still working..."
    mock_response.tool_calls = None
    mock_llm.ainvoke.return_value = mock_response
    
    agent = DeepAgent(
        role="Test",
        objective="Test",
        tools=[],
        max_iterations=3,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    # Always decide to CONTINUE
    with patch.object(agent, '_make_decision') as mock_decision:
        mock_decision.return_value = MagicMock(
            decision_type=AgentDecisionType.CONTINUE,
            reasoning="Keep going",
            confidence=ConfidenceLevel.HIGH,
            next_action="Continue task",
            metadata={},
        )
        
        result = await agent.execute("Long task", {})
        
        assert result["status"] == "max_iterations_reached"
        assert agent.iteration_count == 3


# ============================================================================
# Test Self-Correction
# ============================================================================

@pytest.mark.asyncio
async def test_self_correction_flow():
    """Test agent self-correction."""
    
    mock_llm = AsyncMock()
    
    # First response: needs correction
    first_response = MagicMock()
    first_response.content = "First attempt with errors"
    first_response.tool_calls = None
    
    # Second response: corrected
    second_response = MagicMock()
    second_response.content = "Corrected output"
    second_response.tool_calls = None
    
    mock_llm.ainvoke.side_effect = [first_response, second_response]
    
    agent = DeepAgent(
        role="Self-Correcting Agent",
        objective="Generate valid output",
        tools=[],
        enable_self_correction=True,
        max_iterations=5,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    call_count = 0
    
    async def mock_decision_logic(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(
                decision_type=AgentDecisionType.SELF_CORRECT,
                reasoning="Needs correction",
                confidence=ConfidenceLevel.MEDIUM,
                next_action="",
                metadata={},
            )
        else:
            return MagicMock(
                decision_type=AgentDecisionType.COMPLETE,
                reasoning="Now correct",
                confidence=ConfidenceLevel.HIGH,
                next_action="",
                metadata={},
            )
    
    async def mock_validation(*args, **kwargs):
        if call_count == 1:
            return ValidationResult(
                is_valid=False,
                errors=["Error 1", "Error 2"],
                confidence=ConfidenceLevel.LOW,
            )
        else:
            return ValidationResult(
                is_valid=True,
                confidence=ConfidenceLevel.HIGH,
            )
    
    with patch.object(agent, '_make_decision', side_effect=mock_decision_logic):
        with patch.object(agent, '_validate_output', side_effect=mock_validation):
            result = await agent.execute("Generate output", {})
            
            assert result["status"] == "completed"
            assert agent.iteration_count == 2
            assert result["validation"]["is_valid"] is True


# ============================================================================
# Test Confidence-Based Approval
# ============================================================================

@pytest.mark.asyncio
async def test_low_confidence_requests_approval():
    """Test that low confidence triggers approval request."""
    
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Uncertain output"
    mock_response.tool_calls = None
    mock_llm.ainvoke.return_value = mock_response
    
    agent = DeepAgent(
        role="Uncertain Agent",
        objective="Test",
        tools=[],
        min_confidence_for_autonomy=ConfidenceLevel.HIGH,  # High threshold
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    # Return medium confidence (below threshold)
    with patch.object(agent, '_make_decision') as mock_decision:
        mock_decision.return_value = MagicMock(
            decision_type=AgentDecisionType.REQUEST_APPROVAL,
            reasoning="Confidence too low",
            confidence=ConfidenceLevel.MEDIUM,
            next_action="",
            metadata={},
        )
        
        result = await agent.execute("Uncertain task", {})
        
        assert result["status"] == "requires_approval"
        assert "reasoning" in result


# ============================================================================
# Test Agent Spawning
# ============================================================================

@pytest.mark.asyncio
async def test_agent_spawning():
    """Test spawning sub-agents."""
    
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Main agent output"
    mock_response.tool_calls = None
    mock_llm.ainvoke.return_value = mock_response
    
    agent = DeepAgent(
        role="Parent Agent",
        objective="Complex task",
        tools=[],
        enable_agent_spawning=True,
        max_iterations=5,
    )
    agent.llm = mock_llm
    agent.llm_with_tools = mock_llm
    
    call_count = 0
    
    async def mock_decision_logic(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(
                decision_type=AgentDecisionType.SPAWN_AGENT,
                reasoning="Need specialized help",
                confidence=ConfidenceLevel.HIGH,
                next_action="",
                metadata={
                    "sub_agent_spec": SubAgentSpec(
                        role="Sub Agent",
                        task="Subtask",
                        tools=[],
                        max_iterations=3,
                    )
                },
            )
        else:
            return MagicMock(
                decision_type=AgentDecisionType.COMPLETE,
                reasoning="Done with sub-agent help",
                confidence=ConfidenceLevel.HIGH,
                next_action="",
                metadata={},
            )
    
    with patch.object(agent, '_make_decision', side_effect=mock_decision_logic):
        result = await agent.execute("Complex task", {})
        
        assert result["status"] == "completed"
        assert result["spawned_agents"] == 1
        assert len(agent.spawned_agents) == 1


# ============================================================================
# Test Decision Making
# ============================================================================

@pytest.mark.asyncio
async def test_decision_parsing():
    """Test decision parsing from LLM."""
    
    agent = DeepAgent(
        role="Test",
        objective="Test",
        tools=[],
    )
    
    # Mock LLM to return decision JSON
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '''
```json
{
    "decision": "COMPLETE",
    "reasoning": "Task is finished",
    "confidence": "high",
    "next_action": ""
}
```
'''
    mock_llm.ainvoke.return_value = mock_response
    agent.llm = mock_llm
    
    decision = await agent._make_decision("Test output", {})
    
    assert decision.decision_type == AgentDecisionType.COMPLETE
    assert decision.confidence == ConfidenceLevel.HIGH
    assert "finished" in decision.reasoning.lower()


# ============================================================================
# Test Validation
# ============================================================================

@pytest.mark.asyncio
async def test_validation_result():
    """Test validation result structure."""
    
    validation = ValidationResult(
        is_valid=False,
        errors=["Error 1", "Error 2"],
        warnings=["Warning 1"],
        suggestions=["Fix this", "Improve that"],
        confidence=ConfidenceLevel.MEDIUM,
    )
    
    assert validation.is_valid is False
    assert len(validation.errors) == 2
    assert len(validation.warnings) == 1
    assert len(validation.suggestions) == 2
    assert validation.confidence == ConfidenceLevel.MEDIUM


@pytest.mark.asyncio
async def test_custom_validation_callback():
    """Test custom validation callback."""
    
    async def custom_validator(output: str, context: dict) -> ValidationResult:
        if "good" in output.lower():
            return ValidationResult(is_valid=True, confidence=ConfidenceLevel.HIGH)
        else:
            return ValidationResult(
                is_valid=False,
                errors=["Output doesn't contain 'good'"],
                confidence=ConfidenceLevel.LOW,
            )
    
    agent = DeepAgent(
        role="Test",
        objective="Test",
        tools=[],
        validation_callback=custom_validator,
    )
    
    # Test with good output
    result1 = await agent._validate_output("This is good output", {})
    assert result1.is_valid is True
    
    # Test with bad output
    result2 = await agent._validate_output("This is bad output", {})
    assert result2.is_valid is False
    assert len(result2.errors) > 0


# ============================================================================
# Test Execution History
# ============================================================================

def test_execution_history_tracking():
    """Test that execution history is recorded."""
    
    agent = DeepAgent(
        role="Test",
        objective="Test",
        tools=[],
    )
    
    # Simulate recording steps
    mock_response = MagicMock()
    mock_response.content = "Test response"
    mock_response.tool_calls = None
    
    agent._record_execution_step(mock_response, [])
    agent._record_execution_step(mock_response, [])
    
    assert len(agent.execution_history) == 2
    assert agent.execution_history[0]["iteration"] == 1
    assert agent.execution_history[1]["iteration"] == 2


# ============================================================================
# Integration Test
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_agent_workflow():
    """Integration test of full agent workflow."""
    
    # This test requires actual LLM access
    # Skip if no API key
    import os
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No OpenAI API key available")
    
    @tool
    def save_result(result: str) -> str:
        """Save a result."""
        return f"Saved: {result}"
    
    agent = DeepAgent(
        role="Integration Test Agent",
        objective="Generate a simple greeting and save it",
        tools=[save_result],
        model_name="gpt-4-turbo",
        temperature=0.7,
        max_iterations=5,
        min_confidence_for_autonomy=ConfidenceLevel.LOW,  # Allow autonomy
    )
    
    result = await agent.execute(
        "Generate a friendly greeting message and save it using the tool",
        {},
    )
    
    assert result["status"] in ["completed", "max_iterations_reached"]
    assert len(result["execution_history"]) > 0
    
    # Should have used the tool at some point
    # (we can't guarantee this without inspecting messages)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
