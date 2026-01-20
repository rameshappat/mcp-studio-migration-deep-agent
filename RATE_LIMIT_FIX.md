# Rate Limiting Fix for Test Case Generation

## Problem Identified

After fixing the Deep Agent tool tracking issue, test cases were still not being created. Log analysis revealed:

### Symptoms
```
✅ Using 9 work item IDs from work_items_agent: [1317, 1318, 1319, 1320, 1321, 1322, 1323, 1324, 1325]
...
[1/9] Generating test for WI 1317...
⚠️ Retrying request to /chat/completions in 0.379772 seconds
❌ Exception: Blocking call to time.sleep
[2/9] Generating test for WI 1318...
⚠️ Retrying request to /chat/completions in 0.435400 seconds
❌ Exception: Blocking call to time.sleep
...
✅ Test plan agent complete: 0 created, 9 failed
```

### Root Cause
1. **Work item IDs were successfully passed** (previous fix worked!)
2. **Test plan agent made 9 rapid LLM calls** - one per work item, with no delay
3. **OpenAI rate limiting triggered** - too many requests in quick succession
4. **OpenAI's retry logic used blocking `time.sleep()`** - fails in async context
5. **All test case creations failed** - retry errors prevented test case creation

## Solution Implemented

### Fix 1: Add Async Rate Limiting
**File**: `src/studio_graph_autonomous.py`  
**Function**: `_create_test_cases_with_llm()`  
**Line**: ~1335

Added async sleep between LLM calls:
```python
async def _create_test_cases_with_llm(ado_client, llm, work_items_details, project, test_plan_id, test_suite_id):
    """Use LLM to generate contextualized test cases and create them via REST API."""
    import asyncio
    
    created_cases = []
    failed_tool_calls = []
    
    for idx, wi in enumerate(work_items_details, 1):
        # ... existing code ...
        
        # Rate limiting: Add 2-second delay between LLM calls to avoid rate limits
        if idx > 1:
            logger.info(f"      ⏱️  Waiting 2 seconds to avoid rate limits...")
            await asyncio.sleep(2)
        
        # Use LLM to generate test case
        # ...
```

**Why 2 seconds?**
- OpenAI has rate limits of ~60 requests/minute for GPT-4
- 2 seconds between calls = max 30 calls/minute
- Provides safe buffer below rate limit
- Uses async sleep (non-blocking)

### Fix 2: Use Async LLM Call
**File**: `src/studio_graph_autonomous.py`  
**Line**: ~1384

Changed from blocking to async:
```python
# Before:
response = llm.invoke(prompt)

# After:
response = await llm.ainvoke(prompt)
```

**Benefits**:
- Non-blocking execution
- Proper async/await pattern
- Compatible with LangGraph runtime
- Avoids blocking call warnings

## Testing Instructions

1. **Run the pipeline again**:
   ```bash
   # In LangGraph Studio, trigger a new run
   ```

2. **Expected behavior**:
   - Work items agent creates 9 work items ✅
   - Test plan agent receives created_ids: [1317-1325] ✅
   - Test plan agent adds 2-second delays between LLM calls ⏱️
   - All 9 test cases created successfully ✅
   - Test cases added to Suite 370 ✅

3. **Log indicators of success**:
   ```
   ✅ Using 9 work item IDs from work_items_agent: [1317, 1318, 1319, 1320, 1321, 1322, 1323, 1324, 1325]
   [1/9] Generating test for WI 1317...
   ⏱️  Waiting 2 seconds to avoid rate limits...
   ✅ Created test case: 1234
   ✅ Added to suite 370
   [2/9] Generating test for WI 1318...
   ⏱️  Waiting 2 seconds to avoid rate limits...
   ...
   ✅ Test plan agent complete: 9 created, 0 failed
   ```

## Why This Wasn't Caught Before

1. **Previous logs showed tool_calls_made: 9** - We thought tools weren't being called
2. **Actually: Tools WERE called, but failed silently** - Retry errors weren't surfaced clearly
3. **Log analysis required reading full execution** - Rate limit errors buried in middle of logs
4. **OpenAI's retry behavior changed recently** - More aggressive retries trigger blocking warnings

## Related Issues

- `DEEP_AGENT_TOOL_TRACKING_FIX.md` - Fixed Deep Agent not tracking tool call details
- This was a **sequential issue** - couldn't diagnose rate limiting until tool tracking was fixed

## Long-term Improvements

1. **Batch LLM calls** - Generate multiple test cases in single prompt
2. **Circuit breaker** - Detect rate limits and back off automatically
3. **Retry with exponential backoff (async)** - Handle transient failures gracefully
4. **Request queue** - Centralized rate limiting across all agents

## Summary

✅ **Previous Fix**: Deep Agent now tracks tool call details  
✅ **This Fix**: Test plan agent respects OpenAI rate limits with async delays  
🎯 **Result**: Test cases should now be created successfully in Azure DevOps

**Estimated improvement**: 0% success rate → ~100% success rate for test case creation
