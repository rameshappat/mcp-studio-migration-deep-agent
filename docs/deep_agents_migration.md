# Migration to True Deep Agents - Implementation Guide

## Overview

This document describes the migration from fixed-graph agents to **True Deep Agents** with full autonomy, dynamic routing, and self-correction capabilities.

## Architecture Comparison

### Before: Fixed Graph (studio_graph_agentic.py)

```
┌─────────────────────────────────────────────┐
│          FIXED PIPELINE FLOW                │
├─────────────────────────────────────────────┤
│  Initialize                                 │
│      ↓                                      │
│  Requirements Agent                         │
│      ↓                                      │
│  [Human Approval - REQUIRED]                │
│      ↓                                      │
│  Work Items Agent                           │
│      ↓                                      │
│  [Human Approval - REQUIRED]                │
│      ↓                                      │
│  ADO Push                                   │
│      ↓                                      │
│  Architecture Agent                         │
│      ↓                                      │
│  [Human Approval - REQUIRED]                │
│      ↓                                      │
│  Developer Agent                            │
│      ↓                                      │
│  [Human Approval - REQUIRED]                │
│      ↓                                      │
│  GitHub Push Confirm                        │
│      ↓                                      │
│  GitHub Push                                │
│      ↓                                      │
│  Completed                                  │
└─────────────────────────────────────────────┘

Limitations:
✗ Fixed sequence (cannot skip or reorder)
✗ Human approval required at every stage
✗ Limited tool autonomy (predefined toolsets)
✗ No agent spawning
✗ Limited self-correction
```

### After: Dynamic Graph (studio_graph_deep.py)

```
┌─────────────────────────────────────────────┐
│      DYNAMIC PIPELINE WITH DEEP AGENTS      │
├─────────────────────────────────────────────┤
│  Initialize                                 │
│      ↓                                      │
│  ┌────────────────────┐                     │
│  │  Orchestrator      │◄─────────┐          │
│  │  (Decides Next)    │          │          │
│  └────────────────────┘          │          │
│      ↓         ↓         ↓       │          │
│   Req.     Work     Arch.   Dev  │          │
│   Agent    Items    Agent   Agent│          │
│      │      Agent      │      │  │          │
│      │         │       │      │  │          │
│      └─────────┴───────┴──────┴──┘          │
│                                             │
│  [Human Input - OPTIONAL, confidence-based] │
│                                             │
│  Completed (when Orchestrator decides)      │
└─────────────────────────────────────────────┘

Capabilities:
✓ Dynamic routing (agents decide flow)
✓ Optional approval (confidence-based)
✓ Full tool autonomy
✓ Agent spawning for complex tasks
✓ Automatic self-correction
✓ Can skip/reorder stages
```

## Key Differences

| Feature | Fixed Graph | Deep Agents |
|---------|-------------|-------------|
| **Flow Control** | Hardcoded sequence | Dynamic, LLM-decided |
| **Tool Selection** | Predefined per agent | All tools, LLM chooses |
| **Agent Spawning** | ❌ Not possible | ✅ Recursive spawning |
| **Self-Correction** | Limited validation | Full reflection loop |
| **Human Approval** | ✅ Required | ⚙️ Configurable |
| **Skip Stages** | ❌ Not possible | ✅ Agent decides |
| **Parallel Work** | ❌ Sequential only | ✅ Can spawn parallel |
| **Error Recovery** | Manual intervention | Automatic retry |
| **Confidence** | Not tracked | Explicit levels |
| **Decision Logging** | Basic | Comprehensive |

## New Components

### 1. DeepAgent Class (`src/agents/deep_agent.py`)

Core autonomous agent with:
- **Autonomous tool selection**: LLM chooses tools freely
- **Decision making**: Reflects on output and decides next action
- **Self-correction**: Validates output and automatically fixes issues
- **Agent spawning**: Creates sub-agents for complex subtasks
- **Confidence tracking**: Assesses confidence and requests help when low

```python
agent = DeepAgent(
    role="Requirements Agent",
    objective="Generate comprehensive requirements",
    tools=ALL_TOOLS,  # Has access to all tools
    min_confidence_for_autonomy=ConfidenceLevel.MEDIUM,
    enable_self_correction=True,
    enable_agent_spawning=True,
)

result = await agent.execute(task, context)
```

### 2. Dynamic Graph (`src/studio_graph_deep.py`)

Features:
- **Orchestrator node**: Analyzes state and decides next agent
- **Dynamic routing**: Flow changes based on agent decisions
- **Flexible state**: Tracks arbitrary artifacts
- **Optional interrupts**: Only pauses when confidence is low

### 3. Confidence-Based Approval

```python
# Configuration
state = {
    "require_approval": False,  # Global setting
    "confidence_threshold": "medium",  # minimum for autonomy
}

# Agent behavior
if agent_confidence < threshold:
    return {"status": "requires_approval"}
else:
    proceed_autonomously()
```

## File Structure

```
src/
├── agents/
│   ├── deep_agent.py          # NEW: Core deep agent class
│   ├── base_agent.py           # OLD: Original agent base
│   └── ...
├── studio_graph_agentic.py     # OLD: Fixed graph
├── studio_graph_deep.py        # NEW: Dynamic graph
└── main.py                     # Update to use new graph
```

## Configuration

### Environment Variables

```bash
# Original settings (still used)
OPENAI_API_KEY=sk-...
AZURE_DEVOPS_ORGANIZATION=your-org
AZURE_DEVOPS_PROJECT=your-project
GITHUB_TOKEN=ghp_...

# New settings for deep agents
ENABLE_DEEP_AGENTS=true
CONFIDENCE_THRESHOLD=medium  # very_low, low, medium, high, very_high
REQUIRE_APPROVAL=false       # Set true for manual approval gates
MAX_PIPELINE_ITERATIONS=20   # Prevent infinite loops
ENABLE_AGENT_SPAWNING=true
ENABLE_SELF_CORRECTION=true
```

### Usage

```python
# Old way (fixed graph)
from src.studio_graph_agentic import graph

result = await graph.ainvoke({
    "project_idea": "Build a REST API",
    "project_name": "my-api",
})

# New way (deep agents)
from src.studio_graph_deep import dynamic_graph

result = await dynamic_graph.ainvoke({
    "project_idea": "Build a REST API",
    "project_name": "my-api",
    "require_approval": False,  # Optional
    "confidence_threshold": "medium",  # Optional
    "max_pipeline_iterations": 20,  # Optional
})
```

## Migration Steps

### Phase 1: Side-by-Side (Current)
- ✅ Create deep_agent.py
- ✅ Create studio_graph_deep.py
- ✅ Both graphs available
- Users can choose which to use

### Phase 2: Testing & Validation
- Run both graphs on same project
- Compare outputs and performance
- Tune confidence thresholds
- Validate agent spawning behavior

### Phase 3: Gradual Rollout
- Default to deep agents for new projects
- Keep fixed graph for legacy/conservative use
- Gather user feedback
- Adjust based on real-world usage

### Phase 4: Full Migration (Future)
- Deep agents become default
- Fixed graph deprecated
- Remove old code after transition period

## Agent Capabilities

### Orchestrator
- Analyzes project state
- Decides which agent to run next
- Can skip stages if not needed
- Determines completion criteria
- Manages handoffs

### Requirements Agent
- Gathers requirements autonomously
- Can spawn sub-agents for complex domains
- Self-validates completeness
- Decides if ready to proceed

### Work Items Agent
- Creates epics and stories
- Can interact with ADO directly
- Self-validates story quality
- Adjusts based on feedback

### Architecture Agent
- Designs system architecture
- Generates diagrams autonomously
- Can spawn specialized architects
- Validates design decisions

### Developer Agent
- Implements code
- Runs tests automatically
- Can spawn agents for different modules
- Self-corrects compilation errors
- Pushes to GitHub autonomously

## Self-Correction Flow

```python
# Agent generates output
output = await agent.generate()

# Agent validates its own output
validation = await agent.validate_output(output)

if not validation.is_valid:
    # Agent automatically corrects
    correction_prompt = build_correction_prompt(validation)
    corrected_output = await agent.generate(correction_prompt)
    # Repeat until valid or max attempts
```

## Agent Spawning Example

```python
# Main agent encounters complex subtask
if task_is_complex:
    sub_agent = agent.spawn_sub_agent(
        role="Database Schema Designer",
        task="Design optimal database schema",
        tools=[schema_tools, validation_tools],
        max_iterations=5,
    )
    
    result = await sub_agent.execute()
    
    # Continue with result
    use_result_in_main_task(result)
```

## Decision Types

Agents can make 5 types of decisions:

1. **CONTINUE**: Keep working on current task
2. **COMPLETE**: Task is finished successfully
3. **SELF_CORRECT**: Output needs improvement
4. **SPAWN_AGENT**: Delegate to specialized agent
5. **REQUEST_APPROVAL**: Confidence too low, need human

## Confidence Levels

- **VERY_HIGH**: > 95% confident, proceed autonomously
- **HIGH**: > 80% confident, usually autonomous
- **MEDIUM**: > 60% confident, depends on threshold
- **LOW**: > 40% confident, likely needs approval
- **VERY_LOW**: < 40% confident, definitely needs approval

## Benefits

### For Developers
- Less manual intervention required
- Faster iteration cycles
- Automatic error recovery
- Flexible workflow adaptation

### For Organizations
- Reduced human bottlenecks
- Scalable to complex projects
- Consistent quality through validation
- Audit trail of decisions

### For Users
- More autonomous operation
- Better error handling
- Adaptive to project needs
- Optional control when desired

## Testing

```bash
# Test deep agent directly
python -c "
from src.agents.deep_agent import DeepAgent
from langchain_core.tools import tool

@tool
def test_tool():
    '''Test tool'''
    return 'success'

async def test():
    agent = DeepAgent(
        role='Test',
        objective='Test objective',
        tools=[test_tool],
    )
    result = await agent.execute('Test task')
    print(result)

import asyncio
asyncio.run(test())
"

# Test dynamic graph
python run_sdlc_pipeline.py --use-deep-agents --project "Test API"
```

## Monitoring

Track these metrics:
- Agent decision confidence levels
- Self-correction frequency
- Sub-agent spawn count
- Human intervention rate
- Pipeline iteration count
- Error recovery success rate

## Best Practices

1. **Set appropriate confidence thresholds**
   - Higher for critical systems
   - Lower for exploratory work

2. **Monitor agent spawning**
   - Prevent excessive recursion
   - Set max_iterations appropriately

3. **Enable self-correction**
   - Improves output quality
   - Reduces manual fixes

4. **Use validation callbacks**
   - Custom domain validation
   - Integration with existing tools

5. **Start with approval enabled**
   - Build confidence gradually
   - Disable as you trust the system

## Troubleshooting

### Agent loops infinitely
- Check max_iterations setting
- Review orchestrator decision logic
- Ensure clear completion criteria

### Too many approval requests
- Lower confidence_threshold
- Improve validation logic
- Provide better context

### Poor quality outputs
- Enable self-correction
- Add validation callbacks
- Increase temperature for creativity

### Agent spawning fails
- Check tool availability
- Verify LLM has context
- Review sub-agent specifications

## Future Enhancements

- Multi-agent collaboration (parallel agents)
- Learning from past decisions
- Custom agent training
- Advanced validation strategies
- Integration with more tools
- Performance optimization

## Conclusion

The migration to deep agents transforms the SDLC pipeline from a rigid, manually-supervised process to a flexible, autonomous system that:

✅ Makes intelligent decisions
✅ Corrects its own mistakes  
✅ Spawns specialized help when needed
✅ Adapts to project requirements
✅ Requests help only when necessary

This represents a significant advancement toward truly autonomous software development assistance.
