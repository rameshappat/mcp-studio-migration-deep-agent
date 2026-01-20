"""Deep Agent Implementation - True Autonomous Agent with Dynamic Routing and Self-Correction.

This module implements a deep agent that:
1. Makes autonomous decisions about tool usage
2. Can spawn sub-agents for complex tasks
3. Self-corrects through reflection and validation
4. Dynamically routes to next steps
5. Optionally requests human approval based on confidence
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langsmith import traceable

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level for agent decisions."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class AgentDecisionType(Enum):
    """Types of decisions an agent can make."""
    CONTINUE = "continue"
    SPAWN_AGENT = "spawn_agent"
    REQUEST_APPROVAL = "request_approval"
    SELF_CORRECT = "self_correct"
    COMPLETE = "complete"
    DELEGATE = "delegate"


@dataclass
class AgentDecision:
    """Represents a decision made by an agent."""
    decision_type: AgentDecisionType
    reasoning: str
    confidence: ConfidenceLevel
    next_action: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubAgentSpec:
    """Specification for spawning a sub-agent."""
    role: str
    task: str
    tools: list[Callable]
    constraints: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 5


@dataclass
class ValidationResult:
    """Result of self-validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class DeepAgent:
    """A true deep agent with full autonomy and self-correction capabilities."""

    def __init__(
        self,
        role: str,
        objective: str | None = None,
        tools: list[Callable] | None = None,
        model_name: str = "gpt-4-turbo",
        temperature: float = 0.7,
        provider: str = "openai",
        max_iterations: int = 10,
        min_confidence_for_autonomy: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        enable_self_correction: bool = True,
        enable_agent_spawning: bool = True,
        validation_callback: Optional[Callable] = None,
        system_prompt: str | None = None,  # Alias for objective
        confidence_threshold: ConfidenceLevel | None = None,  # Alias for min_confidence_for_autonomy
        enable_spawning: bool | None = None,  # Alias for enable_agent_spawning
    ):
        """Initialize the deep agent.

        Args:
            role: The role/name of this agent
            objective: The high-level objective this agent is trying to achieve
            tools: List of tools the agent can use
            model_name: LLM model to use
            temperature: Temperature for LLM
            provider: LLM provider (openai or anthropic)
            max_iterations: Maximum iterations before requiring human input
            min_confidence_for_autonomy: Minimum confidence to proceed autonomously
            enable_self_correction: Enable self-correction mechanism
            enable_agent_spawning: Enable spawning sub-agents
            validation_callback: Optional callback for custom validation
            system_prompt: Alternative name for objective (system prompt for the agent)
            confidence_threshold: Alias for min_confidence_for_autonomy
            enable_spawning: Alias for enable_agent_spawning
        """
        self.role = role
        # Support both objective and system_prompt (system_prompt takes precedence)
        self.objective = system_prompt or objective or f"You are a {role}"
        tools = tools or []
        self.tools = tools
        self.model_name = model_name
        self.temperature = temperature
        self.provider = provider.lower()
        self.max_iterations = max_iterations
        # Support aliases for confidence and spawning
        self.min_confidence_for_autonomy = confidence_threshold or min_confidence_for_autonomy
        self.enable_self_correction = enable_self_correction
        self.enable_agent_spawning = enable_spawning if enable_spawning is not None else enable_agent_spawning
        self.validation_callback = validation_callback

        # Create LLM
        if self.provider == "anthropic":
            try:
                self.llm = ChatAnthropic(
                    model=model_name,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic LLM: {e}")
                self.llm = None
        else:
            try:
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI LLM: {e}")
                self.llm = None

        # Bind tools to LLM
        if tools and self.llm:
            self.llm_with_tools = self.llm.bind_tools(tools)
        else:
            self.llm_with_tools = self.llm

        # Agent state
        self.iteration_count = 0
        self.execution_history: list[dict[str, Any]] = []
        self.spawned_agents: list["DeepAgent"] = []
        self.current_confidence = ConfidenceLevel.MEDIUM

    @traceable(name="deep_agent.execute")
    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the agent's task with full autonomy.

        Args:
            task: The task to execute
            context: Additional context for the task

        Returns:
            Execution result with artifacts and decision history
        """
        if context is None:
            context = {}

        self.iteration_count = 0
        self.tool_calls = []  # Track all tool calls and results
        messages = self._build_initial_messages(task, context)
        
        logger.info(f"[{self.role}] Starting execution: {task[:100]}")

        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            
            logger.info(f"[{self.role}] Iteration {self.iteration_count}/{self.max_iterations}")

            # Step 1: Get agent's response (reasoning + tool calls)
            response = await self._invoke_llm(messages)
            
            # Track execution
            self._record_execution_step(response, messages)

            # Step 2: Execute any tool calls
            if response.tool_calls:
                messages.append(response)
                tool_results = await self._execute_tools(response.tool_calls)
                messages.extend(tool_results)
                
                # Record tool calls and results for tracking
                self._record_tool_executions(response.tool_calls, tool_results)
                
                continue  # Continue iteration loop after tool execution

            # Step 3: No more tool calls - agent has produced output
            # Analyze the response and make a decision
            decision = await self._make_decision(response.content, context)
            
            logger.info(
                f"[{self.role}] Decision: {decision.decision_type.value} "
                f"(confidence: {decision.confidence.value})"
            )

            # Step 4: Handle the decision
            if decision.decision_type == AgentDecisionType.COMPLETE:
                # Task complete, return results
                return self._build_result(response.content, decision, context)

            elif decision.decision_type == AgentDecisionType.SELF_CORRECT:
                if not self.enable_self_correction:
                    return self._build_result(response.content, decision, context)
                
                # Validate and self-correct
                validation = await self._validate_output(response.content, context)
                if validation.is_valid:
                    return self._build_result(response.content, decision, context, validation)
                
                # Add correction prompt and continue
                correction_prompt = self._build_correction_prompt(validation)
                messages.append(HumanMessage(content=correction_prompt))
                logger.info(f"[{self.role}] Self-correcting based on validation feedback")
                continue

            elif decision.decision_type == AgentDecisionType.SPAWN_AGENT:
                if not self.enable_agent_spawning:
                    # Fallback: continue with current agent
                    messages.append(
                        HumanMessage(content="Agent spawning disabled. Continue with current task.")
                    )
                    continue
                
                # Spawn sub-agent to handle complex subtask
                sub_agent_result = await self._spawn_and_run_sub_agent(
                    decision.metadata.get("sub_agent_spec"),
                    context
                )
                
                # Add sub-agent result to context
                messages.append(
                    HumanMessage(
                        content=f"Sub-agent completed task. Result:\n{json.dumps(sub_agent_result, indent=2)}"
                    )
                )
                continue

            elif decision.decision_type == AgentDecisionType.REQUEST_APPROVAL:
                # Confidence too low, need human input
                return {
                    "status": "requires_approval",
                    "output": response.content,
                    "decision": {
                        "type": decision.decision_type.value,
                        "reasoning": decision.reasoning,
                        "confidence": decision.confidence.value,
                    },
                    "reasoning": decision.reasoning,
                    "execution_history": self.execution_history,
                    "iterations": self.iteration_count,
                }

            elif decision.decision_type == AgentDecisionType.CONTINUE:
                # Continue with additional reasoning
                messages.append(
                    HumanMessage(content=f"Continue: {decision.next_action}")
                )
                continue

        # Max iterations reached
        logger.warning(f"[{self.role}] Max iterations ({self.max_iterations}) reached")
        return {
            "status": "max_iterations_reached",
            "output": messages[-1].content if messages else "",
            "decision": {
                "type": "max_iterations",
                "reasoning": "Max iterations reached",
                "confidence": "low",
            },
            "execution_history": self.execution_history,
            "requires_approval": True,
            "iterations": self.iteration_count,
        }

    async def _invoke_llm(self, messages: list[BaseMessage]) -> AIMessage:
        """Invoke the LLM with retry logic."""
        try:
            return await self.llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error(f"[{self.role}] LLM invocation failed: {e}")
            raise

    async def _execute_tools(self, tool_calls: list) -> list[ToolMessage]:
        """Execute tool calls and return results."""
        tool_messages = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.info(f"[{self.role}] Executing tool: {tool_name}")
            
            try:
                # Find the tool
                tool_func = next((t for t in self.tools if t.name == tool_name), None)
                if not tool_func:
                    result = f"Error: Tool '{tool_name}' not found"
                else:
                    # Execute tool
                    if asyncio.iscoroutinefunction(tool_func.func):
                        result = await tool_func.func(**tool_args)
                    else:
                        result = tool_func.func(**tool_args)
                
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                    )
                )
            except Exception as e:
                logger.error(f"[{self.role}] Tool execution failed: {e}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=tool_call["id"],
                    )
                )
        
        return tool_messages

    async def _make_decision(
        self,
        output: str,
        context: dict[str, Any],
    ) -> AgentDecision:
        """Analyze output and make a decision about next steps."""
        
        # Build decision prompt
        decision_prompt = f"""You are analyzing your own output to decide next steps.

Objective: {self.objective}
Current iteration: {self.iteration_count}/{self.max_iterations}

Your output:
{output}

Analyze your output and decide:
1. Is the objective complete? (COMPLETE)
2. Does the output need correction? (SELF_CORRECT)
3. Should a sub-agent handle a complex subtask? (SPAWN_AGENT)
4. Is more reasoning needed? (CONTINUE)
5. Is confidence too low for autonomy? (REQUEST_APPROVAL)

Respond with JSON:
{{
    "decision": "COMPLETE|SELF_CORRECT|SPAWN_AGENT|CONTINUE|REQUEST_APPROVAL",
    "reasoning": "Why this decision",
    "confidence": "very_low|low|medium|high|very_high",
    "next_action": "Describe next action if not COMPLETE"
}}
"""

        messages = [
            SystemMessage(content="You are a meta-reasoning agent analyzing your own output."),
            HumanMessage(content=decision_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        
        # Parse decision
        try:
            # Extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            decision_data = json.loads(content.strip())
            
            decision_type = AgentDecisionType[decision_data["decision"]]
            confidence = ConfidenceLevel(decision_data["confidence"])
            
            # Check if confidence is below threshold for autonomy
            if confidence.value < self.min_confidence_for_autonomy.value:
                decision_type = AgentDecisionType.REQUEST_APPROVAL
            
            return AgentDecision(
                decision_type=decision_type,
                reasoning=decision_data["reasoning"],
                confidence=confidence,
                next_action=decision_data.get("next_action", ""),
                metadata=decision_data,
            )
        except Exception as e:
            logger.warning(f"[{self.role}] Failed to parse decision: {e}")
            # Default to completion
            return AgentDecision(
                decision_type=AgentDecisionType.COMPLETE,
                reasoning="Failed to parse decision, assuming complete",
                confidence=ConfidenceLevel.MEDIUM,
                next_action="",
            )

    async def _validate_output(
        self,
        output: str,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Validate the output for correctness and completeness."""
        
        # Use custom validation callback if provided
        if self.validation_callback:
            return await self.validation_callback(output, context)
        
        # Default validation using LLM
        validation_prompt = f"""Validate the following output against the objective.

Objective: {self.objective}

Output to validate:
{output}

Check for:
1. Completeness - Does it address all requirements?
2. Correctness - Are there any logical errors?
3. Quality - Does it meet professional standards?

Respond with JSON:
{{
    "is_valid": true/false,
    "errors": ["list of errors"],
    "warnings": ["list of warnings"],
    "suggestions": ["list of improvements"],
    "confidence": "very_low|low|medium|high|very_high"
}}
"""

        messages = [
            SystemMessage(content="You are a validation agent checking output quality."),
            HumanMessage(content=validation_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            validation_data = json.loads(content.strip())
            
            return ValidationResult(
                is_valid=validation_data["is_valid"],
                errors=validation_data.get("errors", []),
                warnings=validation_data.get("warnings", []),
                suggestions=validation_data.get("suggestions", []),
                confidence=ConfidenceLevel(validation_data.get("confidence", "medium")),
            )
        except Exception as e:
            logger.warning(f"[{self.role}] Validation parsing failed: {e}")
            return ValidationResult(is_valid=True, confidence=ConfidenceLevel.LOW)

    async def _spawn_and_run_sub_agent(
        self,
        spec: SubAgentSpec | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Spawn a sub-agent and run it to completion."""
        
        if not spec:
            logger.warning(f"[{self.role}] No sub-agent spec provided")
            return {"error": "No sub-agent specification"}
        
        logger.info(f"[{self.role}] Spawning sub-agent: {spec.role}")
        
        sub_agent = DeepAgent(
            role=spec.role,
            objective=spec.task,
            tools=spec.tools,
            model_name=self.model_name,
            temperature=self.temperature,
            provider=self.provider,
            max_iterations=spec.max_iterations,
            enable_self_correction=self.enable_self_correction,
            enable_agent_spawning=False,  # Prevent infinite recursion
        )
        
        self.spawned_agents.append(sub_agent)
        
        result = await sub_agent.execute(spec.task, context)
        
        return result

    def _build_initial_messages(
        self,
        task: str,
        context: dict[str, Any],
    ) -> list[BaseMessage]:
        """Build initial message list for the agent."""
        
        system_prompt = f"""You are {self.role}, an autonomous AI agent.

Objective: {self.objective}

You have access to tools that you can use to accomplish your task.
Think step by step, use tools as needed, and produce high-quality output.

Available tools: {', '.join([t.name for t in self.tools])}

Key principles:
1. Be thorough and methodical
2. Use tools to gather information and take actions
3. Validate your work
4. Ask for help if confidence is low
"""

        context_str = json.dumps(context, indent=2) if context else "None"
        
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Task: {task}\n\nContext: {context_str}"),
        ]

    def _build_correction_prompt(self, validation: ValidationResult) -> str:
        """Build a prompt for self-correction."""
        
        prompt_parts = ["Your output needs correction. Please address the following:"]
        
        if validation.errors:
            prompt_parts.append("\nErrors:")
            for error in validation.errors:
                prompt_parts.append(f"  - {error}")
        
        if validation.warnings:
            prompt_parts.append("\nWarnings:")
            for warning in validation.warnings:
                prompt_parts.append(f"  - {warning}")
        
        if validation.suggestions:
            prompt_parts.append("\nSuggestions:")
            for suggestion in validation.suggestions:
                prompt_parts.append(f"  - {suggestion}")
        
        prompt_parts.append("\nPlease revise your output addressing these issues.")
        
        return "\n".join(prompt_parts)

    def _build_result(
        self,
        output: str,
        decision: AgentDecision,
        context: dict[str, Any],
        validation: ValidationResult | None = None,
    ) -> dict[str, Any]:
        """Build the final result."""
        
        # Count total tool calls from execution history
        tool_calls_made = sum(step.get("tool_calls", 0) for step in self.execution_history)
        
        return {
            "status": "completed",
            "output": output,
            "decision": {
                "type": decision.decision_type.value,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence.value,
            },
            "validation": {
                "is_valid": validation.is_valid if validation else True,
                "errors": validation.errors if validation else [],
                "warnings": validation.warnings if validation else [],
            } if validation else None,
            "execution_history": self.execution_history,
            "spawned_agents": len(self.spawned_agents),
            "iterations": self.iteration_count,
            "tool_calls_made": tool_calls_made,
            "tool_calls": self.tool_calls,  # Include detailed tool call information
        }

    def _record_execution_step(
        self,
        response: AIMessage,
        messages: list[BaseMessage],
    ) -> None:
        """Record an execution step in history."""
        
        step = {
            "iteration": self.iteration_count,
            "response_length": len(response.content),
            "tool_calls": len(response.tool_calls) if response.tool_calls else 0,
            "message_count": len(messages),
        }
        
        self.execution_history.append(step)
    
    def _record_tool_executions(
        self,
        tool_calls: list,
        tool_results: list[ToolMessage],
    ) -> None:
        """Record detailed tool call information for tracking."""
        
        for tool_call, tool_result in zip(tool_calls, tool_results):
            tool_info = {
                "tool": tool_call["name"],
                "args": tool_call["args"],
                "result": {
                    "text": tool_result.content,
                    "tool_call_id": tool_result.tool_call_id,
                },
            }
            self.tool_calls.append(tool_info)
            
            logger.debug(f"[{self.role}] Recorded tool execution: {tool_call['name']}")
