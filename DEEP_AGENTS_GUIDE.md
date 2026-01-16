# True Deep Agents - Getting Started

This guide helps you get started with the new **True Deep Agents** implementation.

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run Examples

```bash
# Run interactive examples
python examples_deep_agents.py
```

### 3. Run SDLC Pipeline

```bash
# Deep agents mode (autonomous)
python src/main.py --mode sdlc-deep \
  --project-idea "A REST API for managing tasks" \
  --project-name "task-api"

# Fixed graph mode (traditional)
python src/main.py --mode sdlc-fixed \
  --project-idea "A REST API for managing tasks" \
  --project-name "task-api"
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...                    # Your OpenAI API key

# Optional - Azure DevOps
AZURE_DEVOPS_ORGANIZATION=your-org
AZURE_DEVOPS_PROJECT=your-project
AZURE_DEVOPS_PAT=your-token

# Optional - GitHub
GITHUB_TOKEN=ghp_...
GITHUB_MCP_URL=https://api.githubcopilot.com/mcp/

# Deep Agent Configuration
ENABLE_DEEP_AGENTS=true                  # Enable deep agent mode
CONFIDENCE_THRESHOLD=medium              # very_low|low|medium|high|very_high
REQUIRE_APPROVAL=false                   # Global approval setting
MAX_PIPELINE_ITERATIONS=20               # Max orchestrator iterations
ENABLE_AGENT_SPAWNING=true              # Allow sub-agent creation
ENABLE_SELF_CORRECTION=true             # Auto self-correction

# LLM Configuration
SDLC_LLM_PROVIDER_DEFAULT=openai        # openai or anthropic
OPENAI_MODEL=gpt-4-turbo                # or gpt-4, gpt-3.5-turbo
```

## Usage Examples

### Example 1: Simple Deep Agent

```python
from langchain_core.tools import tool
from src.agents.deep_agent import DeepAgent, ConfidenceLevel

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

agent = DeepAgent(
    role="Weather Assistant",
    objective="Provide weather information",
    tools=[get_weather],
    min_confidence_for_autonomy=ConfidenceLevel.MEDIUM,
)

result = await agent.execute(
    "What's the weather in San Francisco?",
    {}
)

print(result['output'])
```

### Example 2: Dynamic Pipeline

```python
from src.studio_graph_deep import dynamic_graph

initial_state = {
    "project_idea": "A blog platform with user auth",
    "project_name": "my-blog",
    "require_approval": False,
    "confidence_threshold": "medium",
}

config = {
    "configurable": {"thread_id": "my-blog-1"}
}

result = await dynamic_graph.ainvoke(initial_state, config)

print(f"Completed: {result['completed']}")
print(f"Artifacts: {list(result['artifacts'].keys())}")
```

### Example 3: With Custom Validation

```python
from src.agents.deep_agent import DeepAgent, ValidationResult, ConfidenceLevel

async def validate_code(output: str, context: dict) -> ValidationResult:
    """Custom code validation."""
    errors = []
    
    if "TODO" in output:
        errors.append("Code contains TODO comments")
    if "print(" in output and context.get("production"):
        errors.append("Print statements not allowed in production")
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        confidence=ConfidenceLevel.HIGH,
    )

agent = DeepAgent(
    role="Code Generator",
    objective="Generate production code",
    tools=[],
    validation_callback=validate_code,
    enable_self_correction=True,
)

result = await agent.execute(
    "Generate a Python function to calculate fibonacci",
    {"production": True}
)
```

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────┐
│                  Deep Agent                     │
├─────────────────────────────────────────────────┤
│  - Autonomous decision making                   │
│  - Tool selection (all tools available)         │
│  - Self-correction through validation           │
│  - Sub-agent spawning for complex tasks         │
│  - Confidence-based approval                    │
└─────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────┐
│              Dynamic Graph                       │
├─────────────────────────────────────────────────┤
│  Orchestrator → Decides next agent              │
│       ↓                                         │
│  Specialized Agents (Requirements, Arch, etc.)  │
│       ↓                                         │
│  Back to Orchestrator (loop until done)         │
└─────────────────────────────────────────────────┘
```

### Agent Lifecycle

```
1. Initialize
   ↓
2. Execute task
   │
   ├→ Reason about task
   ├→ Select and use tools
   ├→ Generate output
   │
3. Make decision
   │
   ├→ COMPLETE: Done
   ├→ SELF_CORRECT: Validate and fix
   ├→ SPAWN_AGENT: Create sub-agent
   ├→ CONTINUE: More reasoning needed
   └→ REQUEST_APPROVAL: Low confidence
```

## Key Features

### 1. Dynamic Routing

The orchestrator decides which agent to run next:

- Can skip unnecessary stages
- Can reorder based on needs
- Can run same agent multiple times
- Adapts to project complexity

### 2. Full Tool Autonomy

Agents have access to all tools and decide which to use:

- LLM chooses tools freely
- No predefined toolsets per agent
- Can combine tools creatively
- Discovers new tool combinations

### 3. Agent Spawning

Agents can create specialized sub-agents:

```python
# Main agent encounters complex subtask
if needs_specialized_help:
    sub_agent = spawn_sub_agent(
        role="Database Designer",
        task="Design schema",
        tools=[schema_tools],
    )
    result = await sub_agent.execute()
```

### 4. Self-Correction

Automatic validation and correction:

```python
# Agent validates own output
validation = await agent.validate_output()

if not validation.is_valid:
    # Automatically corrects
    corrected = await agent.correct(validation.errors)
```

### 5. Confidence-Based Approval

Only requests approval when uncertain:

```python
if agent.confidence < threshold:
    return {"status": "requires_approval"}
else:
    proceed_autonomously()
```

## Comparison: Fixed vs Deep

| Feature | Fixed Graph | Deep Agents |
|---------|-------------|-------------|
| Flow | Predetermined | Dynamic |
| Approval | Always required | Confidence-based |
| Tools | Limited per agent | All tools available |
| Self-correct | Manual | Automatic |
| Sub-agents | Not possible | Supported |
| Skip stages | No | Yes |

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/test_deep_agents.py -v

# Run specific test
pytest tests/test_deep_agents.py::test_agent_simple_execution -v

# Run with coverage
pytest tests/test_deep_agents.py --cov=src/agents/deep_agent
```

### Integration Tests

```bash
# Requires API keys
export OPENAI_API_KEY=sk-...

# Run integration tests
pytest tests/test_deep_agents.py::test_full_agent_workflow -v -m integration
```

## Monitoring

Track agent behavior:

```python
result = await agent.execute(task, context)

# Check metrics
print(f"Iterations: {result['iterations']}")
print(f"Confidence: {result['decision']['confidence']}")
print(f"Spawned agents: {result['spawned_agents']}")
print(f"Self-corrections: {count_corrections(result['execution_history'])}")
```

## Troubleshooting

### Agent Loops Forever

**Problem**: Agent doesn't complete

**Solutions**:
- Check `max_iterations` setting
- Review agent objective (make it clear and achievable)
- Ensure tools provide useful responses
- Check orchestrator decision logic

### Too Many Approval Requests

**Problem**: Agent always asks for approval

**Solutions**:
- Lower `confidence_threshold`
- Improve agent prompts
- Add better context
- Check validation logic

### Poor Quality Outputs

**Problem**: Generated content is low quality

**Solutions**:
- Enable `enable_self_correction=True`
- Add custom validation callback
- Increase LLM temperature for creativity
- Provide more context in task description

### Agent Spawning Fails

**Problem**: Sub-agents don't work

**Solutions**:
- Verify `enable_agent_spawning=True`
- Check tool availability
- Ensure LLM has proper context
- Review SubAgentSpec configuration

## Best Practices

### 1. Set Clear Objectives

```python
# ✗ Bad
objective = "Do something with the data"

# ✓ Good
objective = "Analyze sales data and generate a summary report with key insights"
```

### 2. Choose Appropriate Confidence Thresholds

```python
# For critical systems
min_confidence_for_autonomy=ConfidenceLevel.VERY_HIGH

# For exploratory work
min_confidence_for_autonomy=ConfidenceLevel.LOW
```

### 3. Provide Rich Context

```python
context = {
    "project_name": "my-app",
    "requirements": {...},
    "constraints": ["must use PostgreSQL", "deploy to AWS"],
    "team_preferences": "TypeScript, React",
}
```

### 4. Monitor and Adjust

```python
# Track performance
if result['iterations'] > 15:
    # Agent is struggling, adjust configuration
    lower_complexity_or_increase_max_iterations()
```

## Advanced Usage

### Custom Decision Logic

```python
class CustomDeepAgent(DeepAgent):
    async def _make_decision(self, output, context):
        # Custom decision logic
        if "database" in output.lower():
            return AgentDecision(
                decision_type=AgentDecisionType.SPAWN_AGENT,
                reasoning="Need DB specialist",
                confidence=ConfidenceLevel.HIGH,
                next_action="",
                metadata={
                    "sub_agent_spec": SubAgentSpec(
                        role="DB Expert",
                        task="Design database",
                        tools=[db_tools],
                    )
                },
            )
        return await super()._make_decision(output, context)
```

### Multi-Agent Collaboration

```python
# Spawn multiple agents in parallel
agents = [
    spawn_agent("Frontend Developer", frontend_task),
    spawn_agent("Backend Developer", backend_task),
    spawn_agent("DevOps Engineer", infra_task),
]

results = await asyncio.gather(*[a.execute() for a in agents])
```

## Migration Path

### Phase 1: Side-by-Side (Current)

Both graphs available:
- Use `--mode sdlc-fixed` for fixed graph
- Use `--mode sdlc-deep` for deep agents
- Compare results on same projects

### Phase 2: Gradual Adoption

- Start with low-risk projects
- Enable deep agents for new projects
- Keep fixed graph for critical systems
- Gather metrics and feedback

### Phase 3: Full Migration

- Deep agents become default
- Fixed graph kept for legacy
- Eventually deprecate fixed graph

## Resources

- **Documentation**: [docs/deep_agents_migration.md](docs/deep_agents_migration.md)
- **Examples**: [examples_deep_agents.py](examples_deep_agents.py)
- **Tests**: [tests/test_deep_agents.py](tests/test_deep_agents.py)
- **Source**: 
  - [src/agents/deep_agent.py](src/agents/deep_agent.py)
  - [src/studio_graph_deep.py](src/studio_graph_deep.py)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review examples and tests
3. Read migration documentation
4. Check agent execution history for insights

## Next Steps

1. ✅ Run examples: `python examples_deep_agents.py`
2. ✅ Try simple pipeline: `python src/main.py --mode sdlc-deep`
3. ✅ Compare modes on same project
4. ✅ Adjust configuration based on needs
5. ✅ Monitor and optimize

Happy building with Deep Agents! 🚀
