# Comprehensive Logging Added - Debugging Guide

## Summary

I've added **extensive detailed logging** throughout the system to help diagnose:
1. **Work Items Creation** - Why only 1 work item ID is being tracked despite 17 being created
2. **Test Case Generation** - Why only 1 test case is being created
3. **Mermaid MCP Failures** - Why architecture diagrams fail with TaskGroup errors

## Files Modified

### 1. `src/agents/deep_agent.py`
**Added logging for:**
- `_build_result()` method:
  - Shows `tool_calls_made` calculation
  - Lists all tool calls executed
  - Displays each tool name and result preview
  
- Tool execution loop:
  - Logs total tool_calls after each execution
  - Shows tool result preview

### 2. `src/studio_graph_autonomous.py`
**Added logging for:**

#### Work Items Agent (`work_items_agent_node`):
- **Line ~1022-1040**: Detailed work items debug section
  - Shows all tool calls made with results
  - Displays tool call count vs created IDs count
  - Lists each tool call with name and result
  
- **Line ~1075-1080**: State return logging
  - Shows `work_items['created_ids']` being returned to state
  - Confirms number of IDs being passed downstream

#### Test Plan Agent (`test_plan_node`):
- **Line ~1291-1300**: Detailed test plan debug section
  - Shows state keys available
  - Displays `work_items_data` type and keys
  - Shows `created_ids` received from state
  
- **Line ~1419-1424**: Work items processing
  - Lists all work items to create test cases for
  - Shows WI ID, type, and title for each

- **Line ~1430-1432**: Test case creation results
  - Shows created test case IDs
  - Displays failed tool calls

- **Line ~1548-1551**: Individual test case creation
  - Shows test title and steps preview
  - Logs ADO API call
  
- **Line ~1558-1560**: Test case creation result
  - Shows ADO result type and content
  - Helps identify API failures

#### Architecture Agent (`architecture_agent_node`):
- **Line ~1689-1697**: Architecture execution
  - Logs start of execution
  - Shows result keys and type
  - Displays output length and preview
  
- **Line ~1705-1709**: Tool calls tracking
  - Lists all tool calls made
  - Identifies Mermaid diagram generation calls

- **Line ~1711-1728**: Mermaid tool failure detection
  - Checks for errors in tool results
  - Logs failed Mermaid tool calls with details

### 3. `src/mcp_client/mermaid_client.py`
**Added logging for:**

#### `call_tool()` method:
- **Start of call**: Tool name and arguments
- **Result processing**:
  - Result type and structure
  - Content availability
  - Text attribute check
  - JSON parsing success/failure
  - Text preview
  
- **Exception handling**:
  - Exception type and message
  - Full traceback
  - Tool name and arguments that caused failure

## What to Look For in Logs

### Work Items Issue:
```
🔍 DETAILED WORK ITEMS DEBUG:
   Tool calls made: 4
   Tool calls list length: 4
   #1: ado_wit_create_work_item -> {"id": 1408, ...}
   #2: ado_wit_create_work_item -> {"id": 1409, ...}
   ...
🔍 CRITICAL: work_items['created_ids'] = [1408, 1409, 1410, ...]
🔍 CRITICAL: Returning work_items with 17 IDs to state
```

Then in test plan agent:
```
🔍 TEST PLAN AGENT DEBUG:
   State keys: ['requirements', 'work_items', ...]
   work_items_data type: <class 'dict'>
   created_ids from state: [1408, 1409, ...]  <-- Should show all IDs
   created_ids length: 17  <-- Should match
```

### Test Case Issue:
```
🤖 Step 2: Using LLM to generate test cases for 17 work items...
🔍 Work items to process:
   1. WI 1408: Epic - Wealth Management Client Onboarding System
   2. WI 1409: Feature - Load Testing and Performance...
   ...
   17. WI 1424: Story - End-to-End System Testing
```

Then for each:
```
  [1/17] Generating test for WI 1408: Wealth Management...
      Title: Test: Wealth Management Client Onboarding System
      Steps preview: 1. Setup test environment...
      Creating test case via ADO REST API...
      🔍 ADO result type: <class 'dict'>
      🔍 ADO result: {'id': 1425, ...}
      ✅ Created test case: 1425
```

### Mermaid Issue:
```
🏗️ Starting architecture agent execution...
[Architect] 🔍 _build_result: tool_calls_made = 3
[Architect] 🔍 Tool calls summary:
[Architect]   #1: mermaid_generate_mermaid_diagram
[Architect]   #2: mermaid_generate_mermaid_diagram
[Architect]   #3: mermaid_generate_mermaid_diagram

🔍 ARCHITECTURE TOOL CALLS - Total: 3
🔍 Tool Call #1: mermaid_generate_mermaid_diagram
...

🎨 MERMAID: call_tool 'mermaid_generate_mermaid_diagram' with args: {...}
🎨 MERMAID: Tool call succeeded, processing result...
🎨 MERMAID: Result type: <class 'CallToolResult'>
🎨 MERMAID: Has content: True
...
❌ MERMAID: call_tool failed with exception: TaskGroup...
```

## How to Use

1. **Stop current LangGraph dev server** (Ctrl+C in terminal)

2. **Restart with logging to file**:
   ```bash
   langgraph dev > log.txt 2>&1
   ```

3. **Run your pipeline in LangGraph Studio**

4. **Check log.txt** for detailed trace:
   ```bash
   # Watch logs in real-time
   tail -f log.txt
   
   # Search for specific issues
   grep "CRITICAL" log.txt
   grep "MERMAID" log.txt
   grep "created_ids" log.txt
   ```

5. **Look for the key indicators**:
   - Work items: Look for `created_ids from state:` in test plan logs
   - Test cases: Look for `Generating test for WI` messages
   - Mermaid: Look for `MERMAID:` prefixed messages and any exceptions

## Expected Outcomes

With these logs, you should now be able to see:

1. **Exactly how many work item IDs** are created and stored
2. **Whether those IDs are passed correctly** to the test plan agent
3. **How many test cases are attempted** for each work item
4. **What Mermaid tool calls are made** and where they fail
5. **Full exception traces** for any Mermaid/MCP failures

## Next Steps

After running with these logs:
1. Share the relevant log sections showing the failures
2. We can identify the exact point where:
   - Work item IDs get lost
   - Test case generation stops
   - Mermaid tool calls fail
3. Apply targeted fixes based on the actual error patterns

---

**Note**: The logs will be verbose, but that's intentional - we need to see the full flow to identify where things break.
