# Deep Agent Tool Tracking Fix

## Problem Summary

The autonomous pipeline was creating work items in Azure DevOps successfully, but the **test plan agent couldn't find them** to create test cases. Analysis revealed two critical bugs:

### Bug #1: Deep Agent Not Recording Tool Call Details
- **Location**: [src/agents/deep_agent.py](src/agents/deep_agent.py)
- **Issue**: The `_record_execution_step()` method only recorded tool call **counts**, not the actual tool call data (tool names, args, results)
- **Impact**: The `work_items_agent_node` couldn't extract work item IDs from tool results because the execution_history didn't contain tool details
- **Evidence**: Logs showed `tool_calls_made: 0` and `created_ids: []` even though work items were created

### Bug #2: Test Plan Agent Not Using created_ids
- **Location**: [src/studio_graph_autonomous.py](src/studio_graph_autonomous.py) 
- **Issue**: The `test_plan_agent_node` was doing its own WIQL query instead of using the `created_ids` list from the work_items agent state
- **Impact**: Even if created_ids were properly populated, test_plan wouldn't use them

## Root Cause

```python
# OLD: _record_execution_step only tracked counts
step = {
    "iteration": self.iteration_count,
    "tool_calls": len(response.tool_calls) if response.tool_calls else 0,  # ❌ Just a count!
}
```

The execution flow was:
1. Deep Agent executes tools successfully ✅
2. Deep Agent logs "Executing tool: ado_wit_create_work_item" ✅
3. Work items created in ADO (IDs 1308-1316) ✅
4. But `_record_execution_step` doesn't save tool call details ❌
5. `work_items_agent_node` parses execution_history, finds no tool data ❌
6. Returns `created_ids: []` to state ❌
7. Test plan agent does WIQL query, doesn't use empty created_ids ❌
8. Result: 0 test cases created ❌

## Solution

### Fix #1: Track Tool Call Details in Deep Agent

**File**: [src/agents/deep_agent.py](src/agents/deep_agent.py)

1. **Added tool_calls list** to track detailed tool execution:
```python
self.tool_calls = []  # Track all tool calls and results
```

2. **Created `_record_tool_executions()` method** to capture full tool data:
```python
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
```

3. **Called `_record_tool_executions()` after tool execution**:
```python
if response.tool_calls:
    messages.append(response)
    tool_results = await self._execute_tools(response.tool_calls)
    messages.extend(tool_results)
    
    # Record tool calls and results for tracking
    self._record_tool_executions(response.tool_calls, tool_results)  # ✅ NEW
    
    continue
```

4. **Returned tool_calls in result dict**:
```python
return {
    "status": "completed",
    "output": output,
    # ... other fields ...
    "tool_calls": self.tool_calls,  # ✅ NEW - Include detailed tool call information
}
```

### Fix #2: Use created_ids in Test Plan Agent

**File**: [src/studio_graph_autonomous.py](src/studio_graph_autonomous.py)

Updated `test_plan_agent_node` to **prioritize created_ids from state**:

```python
# FIRST: Try to use work item IDs from state (created by work_items_agent)
work_items_data = state.get("work_items", {})
created_ids = work_items_data.get("created_ids", [])

if created_ids:
    logger.info(f"   ✅ Using {len(created_ids)} work item IDs from work_items_agent: {created_ids}")
    # Fetch details for each work item created by work_items_agent
    for wi_id in created_ids:
        wi_details = await ado_client.get_work_item(work_item_id=wi_id)
        # ... process work item ...

# FALLBACK: Query ADO if no created_ids
if not work_items_details:
    logger.warning("   ⚠️ No created_ids from work_items_agent, falling back to WIQL query...")
    # ... WIQL query as before ...
```

## Expected Outcome

After these fixes:

1. **Deep Agent** executes tools and records:
   - Tool names: `"ado_wit_create_work_item"`
   - Tool args: `{"project": "testingmcp", "title": "...", ...}`
   - Tool results: Work item IDs in response text

2. **work_items_agent_node** parses `result.get("tool_calls", [])`:
   - Extracts work item IDs: `[1308, 1309, 1310, ...]`
   - Returns `created_ids: [1308, 1309, 1310, ...]`

3. **test_plan_agent_node** reads state:
   - Gets `created_ids` from work_items state
   - Fetches work item details for each ID
   - Generates test cases for those specific work items
   - Creates test cases in ADO Suite 370

## Testing

To verify the fix works:

1. **Run the pipeline** in LangGraph Studio:
   ```bash
   langgraph dev
   ```

2. **Check logs** for these indicators:
   ```
   ✅ Using 9 work item IDs from work_items_agent: [1308, 1309, 1310, ...]
   📋 Work Items Agent: Found 9 work item IDs
   created_ids: [1308, 1309, 1310, ...]
   ```

3. **Verify in Azure DevOps**:
   - Work items 1308-1316 should exist
   - Test Plan 369 / Suite 370 should contain test cases

## Files Changed

- [src/agents/deep_agent.py](src/agents/deep_agent.py) - Added tool call tracking
- [src/studio_graph_autonomous.py](src/studio_graph_autonomous.py) - Use created_ids in test_plan

## Related Issues

- Work items were being created but not tracked
- Test plan couldn't find work items to generate test cases for
- Pipeline appeared to work but produced 0 test cases

## Confirmation

✅ **Work items WERE created** (user confirmed, screenshot shows IDs 1308-1316)  
✅ **Fix implemented** - Deep Agent now tracks tool calls  
✅ **Test plan updated** - Now uses created_ids from state  
✅ **Ready to test** - Next run should create test cases
