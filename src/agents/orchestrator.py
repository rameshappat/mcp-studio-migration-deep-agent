"""Agent Orchestrator for managing multiple agents and workflows."""

import logging
from typing import Any

from langsmith import traceable

from .github_agent import GitHubAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates multiple agents and manages workflow execution."""

    def __init__(self):
        """Initialize the orchestrator."""
        self._agents: dict[str, GitHubAgent] = {}
        self._default_agent: str | None = None

    def register_agent(self, name: str, agent: GitHubAgent, default: bool = False) -> None:
        """Register an agent with the orchestrator.

        Args:
            name: Unique name for the agent.
            agent: The agent instance.
            default: Whether this is the default agent.
        """
        self._agents[name] = agent
        if default or self._default_agent is None:
            self._default_agent = name
        logger.info(f"Registered agent: {name}")

    def get_agent(self, name: str | None = None) -> GitHubAgent | None:
        """Get an agent by name.

        Args:
            name: Agent name, or None for default agent.

        Returns:
            The agent instance, or None if not found.
        """
        if name is None:
            name = self._default_agent
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    @traceable(name="orchestrator.route_request")
    async def route_request(self, user_message: str, agent_name: str | None = None) -> str:
        """Route a user request to the appropriate agent.

        Args:
            user_message: The user's input message.
            agent_name: Optional specific agent to use.

        Returns:
            The agent's response.
        """
        agent = self.get_agent(agent_name)
        if not agent:
            return f"Error: Agent '{agent_name or 'default'}' not found"

        logger.info(f"Routing request to agent: {agent_name or self._default_agent}")
        return await agent.run(user_message)

    @traceable(name="orchestrator.execute_workflow")
    async def execute_workflow(
        self,
        steps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute a multi-step workflow.

        Args:
            steps: List of workflow steps, each with 'agent', 'message', and optional 'depends_on'.

        Returns:
            List of results for each step.
        """
        results = []
        context = {}

        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            agent_name = step.get("agent")
            message_template = step.get("message", "")

            # Interpolate context into message
            message = message_template.format(**context)

            logger.info(f"Executing workflow step: {step_name}")

            try:
                result = await self.route_request(message, agent_name)
                context[step_name] = result
                results.append({
                    "step": step_name,
                    "status": "success",
                    "result": result,
                })
            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                results.append({
                    "step": step_name,
                    "status": "error",
                    "error": str(e),
                })

                # Check if step is required
                if step.get("required", True):
                    break

        return results

    @traceable(name="orchestrator.parallel_execute")
    async def parallel_execute(
        self,
        requests: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Execute multiple requests in parallel.

        Args:
            requests: List of requests with 'agent' and 'message' keys.

        Returns:
            List of results.
        """
        import asyncio

        async def execute_one(req: dict[str, str], idx: int) -> dict[str, Any]:
            try:
                result = await self.route_request(
                    req.get("message", ""),
                    req.get("agent"),
                )
                return {"index": idx, "status": "success", "result": result}
            except Exception as e:
                return {"index": idx, "status": "error", "error": str(e)}

        tasks = [execute_one(req, i) for i, req in enumerate(requests)]
        results = await asyncio.gather(*tasks)

        return sorted(results, key=lambda x: x["index"])
