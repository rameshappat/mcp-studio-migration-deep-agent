"""
Quick Demo of Deep Agents - No API Key Required!

This demo shows the architecture and concepts of deep agents
using mock implementations to work without API keys.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum


class AgentDecisionType(Enum):
    """Types of decisions an agent can make."""
    CONTINUE = "continue"
    COMPLETE = "complete"
    SELF_CORRECT = "self_correct"
    SPAWN_AGENT = "spawn_agent"
    REQUEST_APPROVAL = "request_approval"


class ConfidenceLevel(Enum):
    """Confidence levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class MockAgentResult:
    """Result from a mock agent."""
    status: str
    output: str
    decision_type: AgentDecisionType
    confidence: ConfidenceLevel
    iterations: int
    spawned_agents: int = 0


class MockDeepAgent:
    """Mock deep agent for demonstration."""
    
    def __init__(self, role: str, objective: str, enable_spawning: bool = True):
        self.role = role
        self.objective = objective
        self.enable_spawning = enable_spawning
        self.iteration = 0
        self.spawned_agents = []
    
    async def execute(self, task: str) -> MockAgentResult:
        """Execute the agent's task."""
        self.iteration = 0
        
        print(f"\n{'='*60}")
        print(f"🤖 {self.role}")
        print(f"{'='*60}")
        print(f"Task: {task}")
        print(f"Objective: {self.objective}")
        print()
        
        # Simulate reasoning
        for i in range(3):
            self.iteration += 1
            print(f"  [Iteration {self.iteration}]")
            
            if i == 0:
                print(f"    🧠 Reasoning: Breaking down the task...")
                await asyncio.sleep(0.3)
                print(f"    ✓ Identified key requirements")
                
            elif i == 1:
                print(f"    🛠️  Using tools: Gathering information...")
                await asyncio.sleep(0.3)
                print(f"    ✓ Collected data from tools")
                
                # Maybe spawn a sub-agent
                if self.enable_spawning and "complex" in task.lower():
                    print(f"    🌱 Spawning sub-agent for specialized task...")
                    sub_agent = MockDeepAgent(
                        role="Specialist Agent",
                        objective="Handle complex subtask",
                        enable_spawning=False,
                    )
                    await sub_agent.execute("Handle specialized work")
                    self.spawned_agents.append(sub_agent)
                    print(f"    ✓ Sub-agent completed work")
                
            elif i == 2:
                print(f"    🔍 Self-validating output...")
                await asyncio.sleep(0.3)
                print(f"    ✓ Validation passed")
                
                print(f"\n    🎯 Making decision...")
                print(f"       Decision: COMPLETE")
                print(f"       Confidence: HIGH")
                print(f"       Reasoning: Task successfully accomplished")
        
        print(f"\n✅ Agent completed successfully!")
        print(f"   Iterations: {self.iteration}")
        print(f"   Spawned agents: {len(self.spawned_agents)}")
        
        return MockAgentResult(
            status="completed",
            output=f"{self.role} successfully completed: {task}",
            decision_type=AgentDecisionType.COMPLETE,
            confidence=ConfidenceLevel.HIGH,
            iterations=self.iteration,
            spawned_agents=len(self.spawned_agents),
        )


async def demo_1_simple_agent():
    """Demo 1: Simple autonomous agent."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 1: Simple Autonomous Agent")
    print("="*70)
    print("\nThis agent makes its own decisions without human approval.")
    
    agent = MockDeepAgent(
        role="Requirements Analyst",
        objective="Generate comprehensive requirements",
    )
    
    result = await agent.execute("Analyze requirements for a todo app")
    
    print(f"\n📊 Result:")
    print(f"   Status: {result.status}")
    print(f"   Confidence: {result.confidence.value}")


async def demo_2_agent_with_spawning():
    """Demo 2: Agent that spawns sub-agents."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 2: Agent with Sub-Agent Spawning")
    print("="*70)
    print("\nWhen a task is complex, the agent spawns specialists.")
    
    agent = MockDeepAgent(
        role="Architecture Designer",
        objective="Design complete system architecture",
        enable_spawning=True,
    )
    
    result = await agent.execute("Design a complex microservices architecture")
    
    print(f"\n📊 Result:")
    print(f"   Status: {result.status}")
    print(f"   Spawned agents: {result.spawned_agents}")


async def demo_3_self_correction():
    """Demo 3: Self-correcting agent."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 3: Self-Correction Loop")
    print("="*70)
    print("\nAgent validates its own work and self-corrects.")
    
    print("\n🔄 Self-Correction Process:")
    print("   1. Generate output")
    print("   2. Validate quality")
    print("   3. If errors found → Fix automatically")
    print("   4. Re-validate")
    print("   5. Complete when valid")
    
    agent = MockDeepAgent(
        role="Code Generator",
        objective="Generate high-quality code",
    )
    
    result = await agent.execute("Generate a REST API implementation")
    
    print(f"\n📊 Result:")
    print(f"   Status: {result.status}")
    print(f"   Quality: Validated ✓")


async def demo_4_confidence_based_approval():
    """Demo 4: Confidence-based approval."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 4: Confidence-Based Approval")
    print("="*70)
    print("\nAgent only requests approval when uncertain.\n")
    
    scenarios = [
        ("Simple task", ConfidenceLevel.VERY_HIGH, "Proceed autonomously"),
        ("Moderate task", ConfidenceLevel.HIGH, "Proceed autonomously"),
        ("Complex task", ConfidenceLevel.MEDIUM, "Might request approval"),
        ("Critical decision", ConfidenceLevel.LOW, "Request approval"),
    ]
    
    for task, confidence, action in scenarios:
        print(f"Task: {task}")
        print(f"  Confidence: {confidence.value}")
        print(f"  Action: {action}")
        print()


async def demo_5_dynamic_routing():
    """Demo 5: Dynamic pipeline routing."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 5: Dynamic Pipeline Routing")
    print("="*70)
    print("\nOrchestrator decides the flow dynamically.\n")
    
    print("🎯 Orchestrator analyzing project...")
    await asyncio.sleep(0.5)
    
    print("\n📋 Decided flow for simple project:")
    print("   1. Requirements ✓")
    print("   2. Architecture ✓")
    print("   3. Code ✓")
    print("   4. Skip: Work items (not needed)")
    print("   5. Skip: Manual approval (high confidence)")
    
    print("\n📋 Decided flow for complex project:")
    print("   1. Requirements ✓")
    print("   2. Work Items ✓")
    print("   3. Architecture")
    print("      └─ Spawn: Database Expert")
    print("      └─ Spawn: API Designer")
    print("   4. Code")
    print("      └─ Spawn: Frontend Developer")
    print("      └─ Spawn: Backend Developer")
    print("   5. Human Review (low confidence area)")


async def demo_6_comparison():
    """Demo 6: Fixed vs Dynamic comparison."""
    print("\n" + "="*70)
    print(" "*15 + "DEMO 6: Fixed Graph vs Deep Agents")
    print("="*70)
    
    print("\n📊 FIXED GRAPH (Old Way):")
    print("   Flow: A → B → C → D (always)")
    print("   Tools: Predefined per agent")
    print("   Approval: Required at each stage")
    print("   Self-correction: Manual")
    print("   Agent spawning: Not supported")
    print("   Result: 4 manual approvals required")
    
    print("\n🚀 DEEP AGENTS (New Way):")
    print("   Flow: Dynamic (Orchestrator decides)")
    print("   Tools: All tools available to all agents")
    print("   Approval: Confidence-based (optional)")
    print("   Self-correction: Automatic")
    print("   Agent spawning: Fully supported")
    print("   Result: 0-1 approvals (only if needed)")
    
    print("\n📈 Improvements:")
    print("   ✅ 75% reduction in manual interventions")
    print("   ✅ Automatic error recovery")
    print("   ✅ Adaptive to project complexity")
    print("   ✅ Parallel work via agent spawning")


async def main():
    """Run all demos."""
    print("\n" + "="*70)
    print(" "*20 + "DEEP AGENTS DEMO")
    print(" "*15 + "No API Keys Required!")
    print("="*70)
    print("\nThis demo showcases the architecture and concepts")
    print("of True Deep Agents without needing API credentials.\n")
    
    demos = [
        demo_1_simple_agent,
        demo_2_agent_with_spawning,
        demo_3_self_correction,
        demo_4_confidence_based_approval,
        demo_5_dynamic_routing,
        demo_6_comparison,
    ]
    
    for i, demo in enumerate(demos, 1):
        await demo()
        
        if i < len(demos):
            input(f"\n{'─'*70}\nPress Enter to continue to next demo...")
    
    print("\n" + "="*70)
    print(" "*20 + "DEMO COMPLETE!")
    print("="*70)
    print("\n📚 To use real Deep Agents:")
    print("   1. Set OPENAI_API_KEY environment variable")
    print("   2. Run: python examples_deep_agents.py")
    print("   3. Or run: python src/main.py --mode sdlc-deep")
    print("\n📖 Documentation: DEEP_AGENTS_GUIDE.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
