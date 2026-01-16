# Deep Agents Quick Reference Card

## 🚀 Quick Commands

### Run Demo (No API Key)
```bash
python demo_deep_agents.py
```

### Test Graph Structure
```bash
python test_autonomous_graph.py
```

### Deploy to Studio
```bash
langgraph deploy
```

### Run Studio Locally
```bash
langgraph dev
```

---

## 📋 Graph Selection

In LangSmith Studio, choose:

- **`sdlc_pipeline_autonomous`** ✨ NEW - Deep Agents
- **`sdlc_pipeline_fixed`** - Legacy fixed graph

---

## 🎯 Initial State Format

```json
{
  "user_query": "Your project description here",
  "project_name": "optional-name"
}
```

### Examples:

**Simple:**
```json
{"user_query": "Create a todo app"}
```

**Moderate:**
```json
{"user_query": "Build a REST API with auth"}
```

**Complex:**
```json
{"user_query": "Design microservices e-commerce platform"}
```

---

## 🤖 Available Agents

| Agent | Role | Spawning |
|-------|------|----------|
| **Orchestrator** | Routes & decides | Yes |
| **Requirements** | Gathers requirements | No |
| **Work Items** | Creates epics/stories | No |
| **Architecture** | Designs system | Yes |
| **Developer** | Generates code | Yes |

---

## 🎚️ Confidence Levels

| Level | Range | Behavior |
|-------|-------|----------|
| VERY_HIGH | 95-100% | Always autonomous |
| HIGH | 80-95% | Usually autonomous |
| MEDIUM | 60-80% | May request approval |
| LOW | 40-60% | Often requests approval |
| VERY_LOW | <40% | Always requests approval |

---

## 🔄 Decision Types

1. **COMPLETE** - Task done, proceed
2. **CONTINUE** - Need more work
3. **SELF_CORRECT** - Fix errors found
4. **SPAWN_AGENT** - Create specialist
5. **REQUEST_APPROVAL** - Ask human

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `src/studio_graph_autonomous.py` | Main graph |
| `src/agents/deep_agent.py` | Agent implementation |
| `langgraph.json` | Studio config |
| `.env` | API keys |

---

## 🔧 Environment Variables

### Required:
```bash
OPENAI_API_KEY=sk-...
```

### Recommended:
```bash
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=mcp-sdlc-deep-agents
```

### Optional (for tools):
```bash
AZURE_DEVOPS_ORGANIZATION=...
AZURE_DEVOPS_PROJECT=...
AZURE_DEVOPS_PAT=...
GITHUB_MCP_URL=http://localhost:3000
GITHUB_TOKEN=ghp_...
```

---

## 📊 Expected Flow

### Simple Project
```
Orchestrator → Requirements → Developer → Complete
Time: 2-5 min | Approvals: 0
```

### Moderate Project
```
Orchestrator → Requirements → Architecture → Developer → Complete
Time: 5-10 min | Approvals: 0-1
```

### Complex Project
```
Orchestrator → Requirements → Work Items → 
Architecture (+ spawned) → Developer (+ spawned) → Complete
Time: 10-20 min | Approvals: 1-2
```

---

## 🐛 Quick Troubleshooting

| Issue | Fix |
|-------|-----|
| Graph won't compile | Check `python test_autonomous_graph.py` |
| No API key | Set `OPENAI_API_KEY` in `.env` |
| Too many approvals | Lower confidence thresholds |
| Tools not working | Verify MCP client env vars |
| Orchestrator loops | Check decision history in state |

---

## 📚 Documentation Links

- **Quick Start**: [QUICK_START.md](QUICK_START.md)
- **Studio Guide**: [LANGSMITH_STUDIO_GUIDE.md](LANGSMITH_STUDIO_GUIDE.md)
- **Full Guide**: [DEEP_AGENTS_GUIDE.md](DEEP_AGENTS_GUIDE.md)
- **Comparison**: [BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md)
- **Summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

---

## ⚡ Pro Tips

1. **Start simple** - test with basic projects first
2. **Monitor traces** - use LangSmith to debug
3. **Adjust thresholds** - tune based on your risk tolerance
4. **Watch spawning** - complex projects will create specialists
5. **Check history** - decision_history shows reasoning
6. **Use demo first** - run `demo_deep_agents.py` to understand concepts

---

## 🎯 Success Indicators

You'll know it's working when:
- ✅ Orchestrator makes routing decisions
- ✅ Agents work autonomously
- ✅ Minimal approval requests
- ✅ Self-correction happens automatically
- ✅ Pipeline completes successfully

---

## 🆘 Getting Help

1. Read [LANGSMITH_STUDIO_GUIDE.md](LANGSMITH_STUDIO_GUIDE.md)
2. Check LangSmith traces for errors
3. Run `python test_autonomous_graph.py` to validate setup
4. Review decision history in state
5. Check agent messages for reasoning

---

**Ready to go? Deploy to Studio and try it out!** 🚀

```bash
langgraph deploy
# or
langgraph dev
```

---

**Implementation**: Complete ✅  
**Status**: Production Ready 🚀  
**Version**: 1.0.0
