"""Example: Running Deep Agents

This script demonstrates how to use the new deep agent implementation.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

# Setup
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_simple_deep_agent():
    """Example 1: Create and run a simple deep agent."""
    
    print("\n" + "="*60)
    print("Example 1: Simple Deep Agent")
    print("="*60 + "\n")
    
    from langchain_core.tools import tool
    from src.agents.deep_agent import DeepAgent, ConfidenceLevel
    
    @tool
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"
    
    agent = DeepAgent(
        role="Calculator Agent",
        objective="Perform mathematical calculations accurately",
        tools=[calculate],
        model_name="gpt-4-turbo",
        temperature=0.0,  # Deterministic for math
        max_iterations=3,
        min_confidence_for_autonomy=ConfidenceLevel.MEDIUM,
    )
    
    result = await agent.execute(
        "Calculate the sum of 42 and 58, then multiply the result by 3",
        {}
    )
    
    print(f"Status: {result['status']}")
    print(f"Output: {result['output'][:200]}")
    print(f"Iterations: {result['iterations']}")
    print(f"Decision: {result['decision']}")


async def example_2_self_correcting_agent():
    """Example 2: Agent with self-correction enabled."""
    
    print("\n" + "="*60)
    print("Example 2: Self-Correcting Agent")
    print("="*60 + "\n")
    
    from src.agents.deep_agent import DeepAgent, ConfidenceLevel, ValidationResult
    
    # Custom validation that checks for specific criteria
    async def validate_greeting(output: str, context: dict) -> ValidationResult:
        """Validate that greeting is polite and includes name."""
        
        errors = []
        warnings = []
        
        if "please" not in output.lower() and "thank" not in output.lower():
            warnings.append("Greeting could be more polite")
        
        if context.get("name") and context["name"] not in output:
            errors.append(f"Greeting must include the name '{context['name']}'")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence=ConfidenceLevel.HIGH if is_valid else ConfidenceLevel.LOW,
        )
    
    agent = DeepAgent(
        role="Greeting Generator",
        objective="Generate polite, personalized greetings",
        tools=[],
        enable_self_correction=True,
        validation_callback=validate_greeting,
        max_iterations=5,
    )
    
    result = await agent.execute(
        "Generate a greeting message",
        {"name": "Alice"}
    )
    
    print(f"Status: {result['status']}")
    print(f"Output: {result['output']}")
    print(f"Validation: {result.get('validation')}")
    print(f"Iterations: {result['iterations']}")


async def example_3_agent_spawning():
    """Example 3: Agent that spawns sub-agents."""
    
    print("\n" + "="*60)
    print("Example 3: Agent Spawning")
    print("="*60 + "\n")
    
    from langchain_core.tools import tool
    from src.agents.deep_agent import DeepAgent, ConfidenceLevel
    
    @tool
    def research_topic(topic: str) -> str:
        """Research a topic (simulated)."""
        return f"Research findings on {topic}: [simulated data]"
    
    @tool
    def write_section(title: str, content: str) -> str:
        """Write a section of a document."""
        return f"Section '{title}' written with content: {content[:50]}..."
    
    agent = DeepAgent(
        role="Document Writer",
        objective="Write a comprehensive research document with multiple sections",
        tools=[research_topic, write_section],
        enable_agent_spawning=True,
        max_iterations=8,
    )
    
    result = await agent.execute(
        "Write a research document about renewable energy with sections on solar, wind, and hydro power",
        {}
    )
    
    print(f"Status: {result['status']}")
    print(f"Output length: {len(result['output'])}")
    print(f"Spawned agents: {result['spawned_agents']}")
    print(f"Iterations: {result['iterations']}")


async def example_4_dynamic_pipeline():
    """Example 4: Full dynamic SDLC pipeline."""
    
    print("\n" + "="*60)
    print("Example 4: Dynamic SDLC Pipeline")
    print("="*60 + "\n")
    
    from src.studio_graph_deep import dynamic_graph
    
    # Input configuration
    config = {
        "configurable": {
            "thread_id": "example_4",
        }
    }
    
    # Initial state
    initial_state = {
        "project_idea": "A simple REST API for managing a todo list with CRUD operations",
        "project_name": "todo-api",
        "require_approval": False,  # Fully autonomous
        "confidence_threshold": "medium",
        "max_pipeline_iterations": 15,
    }
    
    print("Starting dynamic pipeline...")
    print(f"Project: {initial_state['project_name']}")
    print(f"Idea: {initial_state['project_idea']}")
    print(f"Approval: {'Required' if initial_state['require_approval'] else 'Autonomous'}")
    print()
    
    try:
        result = await dynamic_graph.ainvoke(initial_state, config)
        
        print("\n" + "-"*60)
        print("Pipeline Result:")
        print("-"*60)
        print(f"Completed: {result.get('completed', False)}")
        print(f"Iterations: {result.get('pipeline_iteration', 0)}")
        print(f"Agents run: {len(result.get('agent_history', []))}")
        print(f"Artifacts created: {len(result.get('artifacts', {}))}")
        
        # Show artifacts
        artifacts = result.get('artifacts', {})
        if artifacts:
            print("\nArtifacts:")
            for artifact_type, artifact_data in artifacts.items():
                print(f"  - {artifact_type}")
        
        # Show agent history
        history = result.get('agent_history', [])
        if history:
            print("\nAgent Execution History:")
            for entry in history:
                agent_name = entry.get('agent', 'unknown')
                iteration = entry.get('iteration', '?')
                print(f"  [{iteration}] {agent_name}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


async def example_5_confidence_based_approval():
    """Example 5: Confidence-based approval."""
    
    print("\n" + "="*60)
    print("Example 5: Confidence-Based Approval")
    print("="*60 + "\n")
    
    from src.agents.deep_agent import DeepAgent, ConfidenceLevel
    
    # High confidence threshold - agent will likely request approval
    agent = DeepAgent(
        role="Critical System Agent",
        objective="Make a critical system decision",
        tools=[],
        min_confidence_for_autonomy=ConfidenceLevel.VERY_HIGH,  # Strict
        max_iterations=3,
    )
    
    result = await agent.execute(
        "Decide whether to deploy the system to production",
        {"system_status": "tests passing, but some warnings"}
    )
    
    print(f"Status: {result['status']}")
    if result['status'] == 'requires_approval':
        print("⚠️  Agent requested human approval due to low confidence")
        print(f"Reasoning: {result.get('reasoning', 'N/A')}")
        print(f"Confidence: {result['decision']['confidence']}")
    else:
        print(f"✅ Agent proceeded autonomously")
        print(f"Output: {result['output'][:200]}")


async def example_6_comparison():
    """Example 6: Compare fixed vs dynamic graph."""
    
    print("\n" + "="*60)
    print("Example 6: Fixed vs Dynamic Graph Comparison")
    print("="*60 + "\n")
    
    project_idea = "A simple calculator web app"
    project_name = "calc-app"
    
    # Note: This is a conceptual comparison
    # In practice, you'd run both and compare results
    
    print("Fixed Graph (studio_graph_agentic.py):")
    print("  - Follows predetermined sequence")
    print("  - Requires human approval at each stage")
    print("  - Limited tool autonomy")
    print("  - Cannot skip stages")
    print("  - No self-correction")
    print()
    
    print("Dynamic Graph (studio_graph_deep.py):")
    print("  - Orchestrator decides flow dynamically")
    print("  - Optional approval based on confidence")
    print("  - Full tool autonomy")
    print("  - Can skip/reorder stages")
    print("  - Automatic self-correction")
    print()
    
    print("For a simple project like a calculator:")
    print("  - Fixed graph: ~5-6 approval gates, linear flow")
    print("  - Dynamic graph: May skip unnecessary stages, 0-2 approval requests")


async def main():
    """Run all examples."""
    
    print("\n" + "="*80)
    print(" "*20 + "DEEP AGENTS EXAMPLES")
    print("="*80)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  Warning: OPENAI_API_KEY not set")
        print("Some examples will be skipped.\n")
        return
    
    examples = [
        ("Simple Deep Agent", example_1_simple_deep_agent),
        ("Self-Correcting Agent", example_2_self_correcting_agent),
        ("Agent Spawning", example_3_agent_spawning),
        ("Dynamic Pipeline", example_4_dynamic_pipeline),
        ("Confidence-Based Approval", example_5_confidence_based_approval),
        ("Comparison", example_6_comparison),
    ]
    
    for i, (name, example_func) in enumerate(examples, 1):
        try:
            print(f"\n[{i}/{len(examples)}] Running: {name}")
            await example_func()
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(examples):
            print("\n" + "-"*80)
            input("Press Enter to continue to next example...")
    
    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
