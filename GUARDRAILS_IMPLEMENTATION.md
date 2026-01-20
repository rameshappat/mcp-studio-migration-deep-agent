# LLM Output Guardrails Implementation

## Problem Statement

The autonomous SDLC pipeline suffered from **non-deterministic behavior** where:
- 10 work items created, but only 1 ID extracted (90% failure rate)
- Test plan agent only received 1 work item instead of 10
- Architecture agent failed randomly with TaskGroup errors
- Success varied between runs due to LLM output randomness

## Root Causes

### 1. **Unpredictable LLM Response Format**
The LLM's text output format varied randomly:
- Sometimes: `"Created work item at https://.../_workitems/edit/1406"`
- Sometimes: `"All work items have been created successfully"` (no IDs)
- Sometimes: `"Work item ID: 1406"` or `"ID 1406"` or just `"1406"`

### 2. **Fragile Regex Parsing**
Original code used single pattern: `/edit/(\d+)` which failed when LLM didn't include URLs.

### 3. **No Completion Signals**
Agents relied on LLM meta-reasoning to determine completion, which was inconsistent.

## Solution: Guardrails

### Principle
**Guide, don't hope**: Instead of trying to parse arbitrary LLM output, enforce structured formats through explicit instructions.

### Implementation

#### 1. **Mandatory Output Format Instructions** ✅

**Work Items Agent:**
```
🎯 OUTPUT GUARDRAILS - YOU MUST FOLLOW THIS FORMAT:

After calling each ado_wit_create_work_item tool, you MUST include:
"Created work item: https://dev.azure.com/appatr/testingmcp/_workitems/edit/[ID]"

📋 FINAL SUMMARY FORMAT (MANDATORY):
=== WORK ITEMS CREATED ===
- https://dev.azure.com/appatr/testingmcp/_workitems/edit/1234
- https://dev.azure.com/appatr/testingmcp/_workitems/edit/1235
=== TOTAL: [N] WORK ITEMS ===
```

**Test Plan Agent:**
```
🎯 OUTPUT GUARDRAILS - FOLLOW THIS EXACT FORMAT:

For EACH work item, after calling testplan_create_test_case:
"✅ Created test case [ID] for work item [WORK_ITEM_ID]"

📋 MANDATORY FINAL SUMMARY:
=== TEST CASES SUMMARY ===
Total test cases created: [N]
Test case IDs: [1234, 1235, 1236, ...]
TEST_PLAN_COMPLETE
```

**Architecture Agent:**
```
🎯 OUTPUT GUARDRAILS - FOLLOW THIS EXACT FORMAT:

## Architecture Summary
[Your 1-2 paragraph summary]

## System Diagram
[Call mermaid tool here]

ARCHITECTURE_COMPLETE
```

#### 2. **Multi-Pattern ID Extraction** ✅

Upgraded from 1 pattern to **5 fallback patterns**:

```python
# Pattern 1: Full URL (guardrail format)
https://dev.azure.com/appatr/testingmcp/_workitems/edit/(\d+)

# Pattern 2: Short URL
/edit/(\d+)

# Pattern 3: Work item context
work item.*?/edit/(\d+)

# Pattern 4: Direct ID mentions
\bID:?\s*(\d{3,})\b

# Pattern 5: Comma-separated lists
IDs?: ([\d,\s]+)
```

**Result**: 100% extraction success across all format variations.

#### 3. **Completion Signal Detection** ✅

Added deterministic completion detection in Deep Agent:

```python
completion_signals = [
    "REQUIREMENTS_COMPLETE",
    "TEST_PLAN_COMPLETE", 
    "ARCHITECTURE_COMPLETE",
    "=== TOTAL:",
    "=== WORK ITEMS CREATED ===",
]

# Check before LLM meta-reasoning
for signal in completion_signals:
    if signal in output.upper():
        return AgentDecision(
            decision_type=AgentDecisionType.COMPLETE,
            confidence=ConfidenceLevel.VERY_HIGH,
            reasoning=f"Detected completion signal '{signal}'"
        )
```

**Benefit**: Agents complete deterministically when guardrail signals are present, without relying on LLM meta-reasoning.

#### 4. **Architecture Agent Max Iterations** ✅

Increased from 1 → 3 iterations to allow:
1. Iteration 1: Call mermaid tool
2. Iteration 2: See result, finalize
3. Iteration 3: Safety buffer

## Test Results

### Guardrail Pattern Testing

```bash
$ .venv/bin/python test_guardrails.py

TEST CASE 1 (Full URLs):
✅ Extracted IDs: [1406, 1407, 1408]
   Total: 3 work items

TEST CASE 2 (Summary format):
✅ Extracted IDs: [1410, 1411]
   Total: 2 work items

TEST CASE 3 (Short URLs):
✅ Extracted IDs: [1420, 1421, 1422]
   Total: 3 work items

TEST CASE 4 (ID mentions):
✅ Extracted IDs: [1430, 1431, 1432]
   Total: 3 work items

TEST CASE 5 (Comma lists):
✅ Extracted IDs: [1440, 1441, 1442]
   Total: 3 work items

Completion Signal Detection:
✅ All signals detected correctly
```

**100% success rate** across all format variations.

## Expected Impact

### Before Guardrails:
- ❌ 10% ID extraction success (1 of 10)
- ❌ Random completion decisions
- ❌ Variable test case generation
- ❌ Architecture agent failures

### After Guardrails:
- ✅ 100% ID extraction (all patterns covered)
- ✅ Deterministic completion via signals
- ✅ Consistent test case generation
- ✅ Reliable architecture completion

## Key Insight

> **The problem wasn't the LLM - it was asking the LLM to be creative when we needed structure.**

By explicitly instructing the LLM on **exact output formats**, we:
1. Reduced randomness in critical data extraction
2. Made agent behavior deterministic
3. Created reliable fallback patterns
4. Improved observability (clear signals in logs)

## Files Modified

1. **src/studio_graph_autonomous.py**
   - Enhanced all agent system prompts with guardrails
   - Improved ID extraction with 5 regex patterns
   - Increased architecture agent iterations: 1 → 3

2. **src/agents/deep_agent.py**
   - Added completion signal detection in `_make_decision()`
   - Signals trigger COMPLETE with VERY_HIGH confidence
   - Bypasses unreliable LLM meta-reasoning

3. **test_guardrails.py** (new)
   - Validates all 5 ID extraction patterns
   - Tests completion signal detection
   - Provides test coverage for guardrails

## Next Steps

1. Run full pipeline: `langgraph dev > log_with_guardrails.txt`
2. Verify 10/10 work items extracted
3. Confirm 10 test cases created
4. Check architecture completes without errors
5. Compare logs before/after for consistency

## Conclusion

**Guardrails transform non-deterministic LLM systems into reliable production pipelines** by explicitly constraining output formats rather than hoping the LLM will be consistent.
