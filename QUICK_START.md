# Deep Agents - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. See It in Action (No API Key)
```bash
python demo_deep_agents.py
```
Interactive demo showing all capabilities without needing credentials.

### 2. Set Up Environment
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run with Real LLM
```bash
# Set your API key
export OPENAI_API_KEY="sk-..."

# Run examples
python examples_deep_agents.py

# Or run the full system
python src/main.py --mode sdlc-deep --query "Create a todo app"
```

---

## 📚 What You Get

### True Deep Agents
- **Autonomous Decision-Making**: Agents decide next steps independently
- **Self-Correction**: Automatic error detection and fixing
- **Agent Spawning**: Create specialists on-demand
- **Confidence-Based Approval**: Only asks humans when uncertain
- **Dynamic Routing**: Flow adapts to project needs

### Old vs New

| Feature | Fixed Graph | Deep Agents |
|---------|------------|-------------|
| Flow | Static (A→B→C→D) | Dynamic |
| Tools | Per-agent | All available |
| Approval | Always required | Optional |
| Self-fix | Manual | Automatic |
| Spawning | ❌ | ✅ |

---

## 💡 Usage Examples

### Example 1: Simple Task
```python
from src.agents.deep_agent import DeepAgent

agent = DeepAgent(
    role="Requirements Analyst",
    objective="Generate requirements",
)

result = await agent.execute("Create requirements for a todo app")
```

### Example 2: With Sub-Agents
```python
agent = DeepAgent(
    role="Architect",
    objective="Design system",
    enable_spawning=True,  # Can spawn specialists
)

result = await agent.execute("Design microservices architecture")
# Agent spawns database expert, API designer, etc.
```

### Example 3: Full Pipeline
```python
from src.studio_graph_deep import build_dynamic_graph

# Build the graph
app = build_dynamic_graph()

# Run it
result = await app.ainvoke({
    "user_query": "Build an e-commerce platform",
    "project_context": {}
})
```

---

## 🎯 Command Line Usage

### Mode Selection
```bash
# Deep agents (new)
python src/main.py --mode sdlc-deep --query "Your task"

# Fixed pipeline (old)
python src/main.py --mode sdlc-fixed --query "Your task"

# Single agent
python src/main.py --mode agent --query "Your task"
```

### Approval Thresholds
```bash
# Require approval for medium+ confidence
python src/main.py --mode sdlc-deep --approval-threshold medium

# Require approval for low+ confidence
python src/main.py --mode sdlc-deep --approval-threshold low

# No approvals (full autonomy)
python src/main.py --mode sdlc-deep --approval-threshold never
```

---

## 🧪 Testing

### Run Demo
```bash
python demo_deep_agents.py
```

### Run Unit Tests
```bash
pytest tests/test_deep_agents.py -v
```

### Run Specific Examples
```bash
python examples_deep_agents.py
# Then select example number when prompted
```

---

## 🔧 Configuration

### LLM Provider
Edit `src/config.py`:
```python
# Use OpenAI (default)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = "gpt-4-turbo-preview"

# Or use Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_MODEL = "claude-3-sonnet-20240229"
```

### Agent Behavior
```python
agent = DeepAgent(
    role="Developer",
    objective="Generate code",
    max_iterations=5,           # Stop after 5 attempts
    confidence_threshold="high", # Request approval if below
    enable_spawning=True,       # Allow sub-agents
    tools=[...],                # Available tools
)
```

---

## 📊 Key Features

### 1. Five Decision Types
- **COMPLETE**: Task done, proceed
- **CONTINUE**: Need more iterations
- **SELF_CORRECT**: Fix errors found
- **SPAWN_AGENT**: Create specialist
- **REQUEST_APPROVAL**: Ask human

### 2. Confidence Levels
- **VERY_HIGH**: 95-100% certain
- **HIGH**: 80-95% certain
- **MEDIUM**: 60-80% certain
- **LOW**: 40-60% certain
- **VERY_LOW**: Below 40% certain

### 3. Agent Spawning
```python
# Parent agent decides to spawn
if task_is_complex:
    sub_agent = spawn_agent(
        role="Database Expert",
        objective="Design schema"
    )
    result = await sub_agent.execute(subtask)
```

### 4. Self-Correction
```python
# Agent validates its own output
validation = agent._validate_output(output)
if not validation.is_valid:
    # Automatically fix
    output = agent._self_correct(output, validation.errors)
```

---

## 🎓 Learning Path

### Beginner
1. ✅ Run `demo_deep_agents.py`
2. ✅ Read `DEEP_AGENTS_GUIDE.md`
3. ✅ Try Example 1 in `examples_deep_agents.py`

### Intermediate
4. ✅ Run full pipeline with real LLM
5. ✅ Read `deep_agents_migration.md`
6. ✅ Try Examples 2-4

### Advanced
7. ✅ Study `src/agents/deep_agent.py`
8. ✅ Study `src/studio_graph_deep.py`
9. ✅ Create custom agents
10. ✅ Extend with new tools

---

## 🔍 Architecture Overview

```
┌─────────────────────────────────────────┐
│         User Query                       │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│     Orchestrator Agent                   │
│  • Analyzes request                      │
│  • Decides flow dynamically              │
│  • Routes to specialists                 │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│ Requirements │  │ Architecture │
│    Agent     │  │    Agent     │
└──────┬───────┘  └───────┬──────┘
       │                  │
       │    ┌─────────────┘
       │    │
       ▼    ▼
   ┌──────────────┐
   │  Developer   │
   │    Agent     │
   └──────────────┘
```

Each agent can:
- Make independent decisions
- Use any tool
- Spawn sub-agents
- Self-correct errors
- Request approval if uncertain

---

## 📝 Common Scenarios

### Scenario 1: Simple Feature
```bash
python src/main.py --mode sdlc-deep \
  --query "Add user authentication to existing app"
```
**Flow:** Requirements → Code (2 agents, ~2-5 min)

### Scenario 2: New Microservice
```bash
python src/main.py --mode sdlc-deep \
  --query "Create a new payment processing microservice"
```
**Flow:** Requirements → Architecture → Code (3 agents, spawning, ~5-10 min)

### Scenario 3: Complex System
```bash
python src/main.py --mode sdlc-deep \
  --query "Design and implement a scalable e-commerce platform"
```
**Flow:** Full pipeline with work items, multiple spawns (~10-20 min)

---

## ⚙️ Customization

### Custom Agent
```python
from src.agents.deep_agent import DeepAgent

custom_agent = DeepAgent(
    role="Security Expert",
    objective="Perform security audit",
    system_prompt="""
    You are a security expert. Always:
    - Check for common vulnerabilities
    - Validate input sanitization
    - Review authentication/authorization
    """,
    tools=[security_scan_tool, vulnerability_check_tool],
)
```

### Custom Validation
```python
def my_validation_callback(output: str) -> ValidationResult:
    # Custom validation logic
    if "TODO" in output:
        return ValidationResult(
            is_valid=False,
            errors=["Contains TODO placeholders"]
        )
    return ValidationResult(is_valid=True)

agent = DeepAgent(
    role="Developer",
    validation_callback=my_validation_callback,
)
```

---

## 🐛 Troubleshooting

### Issue: API Key Not Found
```bash
export OPENAI_API_KEY="your-key-here"
# Or create .env file:
echo "OPENAI_API_KEY=your-key" > .env
```

### Issue: Import Errors
```bash
pip install -r requirements.txt --force-reinstall
```

### Issue: Agent Not Autonomous
Check configuration:
```python
# Ensure these are set
enable_spawning=True
confidence_threshold="high"  # Not "very_high"
max_iterations=10  # High enough
```

### Issue: Too Many Approvals
Lower the threshold:
```bash
python src/main.py --approval-threshold very_low
```

---

## 📈 Performance Tips

1. **Use GPT-4-Turbo** (faster than GPT-4)
2. **Enable Caching** (reduce API calls)
3. **Set Max Iterations** (prevent runaway)
4. **Use Spawning Judiciously** (parallel work)
5. **Monitor with LangSmith** (observability)

---

## 🤝 Contributing

### Run Tests Before Committing
```bash
pytest tests/ -v
python demo_deep_agents.py  # Should complete
```

### Code Style
```bash
black src/ tests/
pylint src/agents/deep_agent.py
```

---

## 📚 Documentation

- **Overview**: `README.md`
- **Full Guide**: `DEEP_AGENTS_GUIDE.md`
- **Migration**: `deep_agents_migration.md`
- **Testing**: `TESTING_AND_VALIDATION.md`
- **Architecture**: `docs/architecture_and_design.md`

---

## 🎉 Success!

You're now ready to use True Deep Agents! Start with the demo, then move to real LLM usage.

**Next Steps:**
1. Run demo to understand concepts
2. Set API key and try examples
3. Run full pipeline on your project
4. Customize agents for your needs

Happy building! 🚀
