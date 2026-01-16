# Running Deep Agents in LangSmith Studio

This guide explains how to deploy and run the Autonomous SDLC Pipeline in LangSmith Studio.

## 🎯 Overview

You now have **two graph options** available in Studio:

1. **`sdlc_pipeline_fixed`** - Original fixed graph (legacy)
2. **`sdlc_pipeline_autonomous`** - New Deep Agents (recommended)

## 🚀 Quick Start

### 1. Prerequisites

Ensure your `.env` file has all required API keys:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional but recommended
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=mcp-sdlc-deep-agents

# For ADO integration
AZURE_DEVOPS_ORGANIZATION=your-org
AZURE_DEVOPS_PROJECT=your-project
AZURE_DEVOPS_PAT=your-pat

# For GitHub integration
GITHUB_MCP_URL=http://localhost:3000
GITHUB_TOKEN=ghp_...
```

### 2. Deploy to Studio

```bash
# Make sure you're in the project directory
cd /Users/rameshappat/Downloads/mcp-studio-migration-deep-agent

# Deploy to LangSmith Studio
langgraph deploy
```

Or run locally:

```bash
langgraph dev
```

### 3. Access Studio

1. Open LangSmith Studio: https://smith.langchain.com/studio
2. Select your graph: `sdlc_pipeline_autonomous`
3. Start a new thread

### 4. Start a Pipeline

In Studio, provide this initial state:

```json
{
  "user_query": "Create a REST API for managing todo items with CRUD operations",
  "project_name": "todo-api"
}
```

### 5. Watch the Magic ✨

The orchestrator will:
1. Analyze your requirements
2. Decide which agents to invoke
3. Route dynamically based on complexity
4. Only request approval when uncertain
5. Self-correct errors automatically

## 📊 Understanding the Flow

### Autonomous Graph Flow

```
START
  ↓
Orchestrator (decides next step)
  ↓
  ├──→ Requirements Agent (if needed)
  │      ↓
  │    Orchestrator (re-evaluate)
  │
  ├──→ Work Items Agent (if complex)
  │      ↓
  │    Orchestrator (re-evaluate)
  │
  ├──→ Architecture Agent (if needed)
  │      ↓
  │    Orchestrator (re-evaluate)
  │
  ├──→ Developer Agent (always)
  │      ↓
  │    Orchestrator (re-evaluate)
  │
  └──→ Complete (when done)
         ↓
       END
```

### Decision Flow

At each step, the orchestrator:
1. Reviews what's been completed
2. Analyzes project complexity
3. Decides next agent
4. Routes accordingly

Agents can:
- **Self-correct**: Fix their own errors
- **Spawn sub-agents**: Create specialists
- **Request approval**: Only if uncertain
- **Skip stages**: If not needed

## 🎮 Example Scenarios

### Scenario 1: Simple Project

```json
{
  "user_query": "Create a basic todo app with add/delete functions"
}
```

**Expected Flow:**
- Orchestrator → Requirements → Developer → Complete
- Time: ~2-5 minutes
- Approvals: 0

### Scenario 2: Moderate Project

```json
{
  "user_query": "Build a REST API for a task management system with user authentication"
}
```

**Expected Flow:**
- Orchestrator → Requirements → Architecture → Developer → Complete
- Time: ~5-10 minutes
- Approvals: 0-1 (if low confidence on auth)

### Scenario 3: Complex Project

```json
{
  "user_query": "Design and implement a microservices-based e-commerce platform with payment processing"
}
```

**Expected Flow:**
- Orchestrator → Requirements → Work Items → Architecture (spawns DB Expert, API Designer) → Developer (spawns Frontend, Backend, DevOps) → Complete
- Time: ~10-20 minutes
- Approvals: 1-2 (critical decisions)

## 🔍 Monitoring in Studio

### View Agent Decisions

In Studio, you can see:
- Current agent
- Decision reasoning
- Confidence levels
- Spawned sub-agents
- Error recovery attempts

### Check State

State includes:
```json
{
  "requirements": {...},
  "work_items": {...},
  "architecture": {...},
  "code_artifacts": {...},
  "decision_history": [...],
  "messages": [...]
}
```

### Follow Message Trail

Messages show:
- Agent actions
- Decisions made
- Confidence levels
- Approval requests

## ⚙️ Customization

### Adjust Confidence Thresholds

Edit agent creation in `src/studio_graph_autonomous.py`:

```python
def create_requirements_agent() -> DeepAgent:
    return DeepAgent(
        role="Requirements Analyst",
        # ... other params ...
        confidence_threshold=ConfidenceLevel.VERY_HIGH,  # More approvals
        # or
        confidence_threshold=ConfidenceLevel.LOW,  # Fewer approvals
    )
```

### Enable/Disable Spawning

```python
def create_architecture_agent() -> DeepAgent:
    return DeepAgent(
        # ... other params ...
        enable_spawning=False,  # Disable sub-agent creation
    )
```

### Change Max Iterations

```python
def create_developer_agent() -> DeepAgent:
    return DeepAgent(
        # ... other params ...
        max_iterations=10,  # Allow more self-correction attempts
    )
```

## 🐛 Troubleshooting

### Issue: Orchestrator doesn't route

**Cause:** LLM not returning expected format
**Fix:** Check orchestrator_node parsing logic

### Issue: Agents request too many approvals

**Cause:** Confidence threshold too high
**Fix:** Lower threshold to HIGH or MEDIUM

### Issue: Pipeline doesn't complete

**Cause:** Orchestrator stuck in loop
**Fix:** Check orchestrator decision logic in state

### Issue: Tools not working

**Cause:** MCP clients not initialized
**Fix:** Verify .env has correct credentials

## 📈 Performance Tips

1. **Use GPT-4-Turbo** for faster responses
2. **Lower confidence thresholds** for fewer interruptions
3. **Disable spawning** for simple projects
4. **Monitor LangSmith traces** to identify bottlenecks

## 🔄 Switching Between Graphs

### To use Fixed Graph (legacy):

```bash
# In Studio, select: sdlc_pipeline_fixed
```

### To use Autonomous Graph (new):

```bash
# In Studio, select: sdlc_pipeline_autonomous
```

## 📚 Comparison

| Feature | Fixed Graph | Autonomous Graph |
|---------|------------|------------------|
| Flow | Static | Dynamic |
| Approvals | 4 required | 0-2 optional |
| Time | 10-30 min | 2-10 min |
| Agent Spawning | ❌ | ✅ |
| Self-Correction | ❌ | ✅ |
| Complexity Adaptation | ❌ | ✅ |

## 🎯 Best Practices

1. **Start with small projects** to understand the flow
2. **Monitor decision history** to see agent reasoning
3. **Adjust confidence thresholds** based on your risk tolerance
4. **Use LangSmith tracing** to debug issues
5. **Review spawned agents** to understand specialization

## 🚀 Advanced Usage

### Custom System Prompts

Modify agent creation functions to add domain-specific instructions:

```python
def create_architecture_agent() -> DeepAgent:
    return DeepAgent(
        role="Architect",
        system_prompt="""You are a Software Architect specializing in fintech.
        
        Always consider:
        - PCI-DSS compliance
        - Data encryption
        - Audit trails
        - High availability
        
        [... rest of prompt ...]
        """,
        # ... other params ...
    )
```

### Add Custom Validators

```python
def my_custom_validator(output: str) -> ValidationResult:
    # Custom validation logic
    if "security" not in output.lower():
        return ValidationResult(
            is_valid=False,
            errors=["Missing security considerations"]
        )
    return ValidationResult(is_valid=True)

agent = DeepAgent(
    # ... other params ...
    validation_callback=my_custom_validator,
)
```

## 📞 Support

- **Documentation**: See other .md files in project root
- **Issues**: Check logs in LangSmith Studio
- **Debugging**: Enable DEBUG logging in .env

## 🎉 Success Indicators

You'll know it's working when:
- ✅ Orchestrator makes routing decisions
- ✅ Agents complete tasks autonomously
- ✅ Minimal approval requests
- ✅ Self-correction happens automatically
- ✅ Pipeline completes end-to-end

## 🔗 Related Documentation

- [DEEP_AGENTS_GUIDE.md](DEEP_AGENTS_GUIDE.md) - Full guide
- [QUICK_START.md](QUICK_START.md) - Quick start
- [BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md) - Comparison
- [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) - Migration summary

---

**You're ready to run autonomous SDLC pipelines in LangSmith Studio!** 🚀
