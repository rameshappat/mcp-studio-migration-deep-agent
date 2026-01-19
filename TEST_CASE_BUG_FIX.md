# Test Case Generation Bug - Root Cause Analysis and Fix

## Problem
Test cases were being created as work items but NOT appearing in Test Suite 370 in Azure DevOps.

## Root Cause
The `testplan_add_test_cases_to_suite` MCP tool has **strict parameter requirements** that were NOT being followed:

### ❌ WRONG (What the code was doing):
```python
await client.call_tool('testplan_add_test_cases_to_suite', {
    'project': 'testingmcp',
    'test_plan_id': 369,        # ❌ Wrong parameter name (snake_case)
    'test_suite_id': 370,        # ❌ Wrong parameter name (snake_case)
    'test_case_ids': [1163]      # ❌ Wrong type (number array instead of string)
})
```

### ✅ CORRECT (What it should be):
```python
await client.call_tool('testplan_add_test_cases_to_suite', {
    'project': 'testingmcp',
    'planId': 369,               # ✅ camelCase
    'suiteId': 370,              # ✅ camelCase
    'testCaseIds': "1163"        # ✅ STRING (or array of strings ["1163"])
})
```

## Tool Schema (from MCP Server)
```json
{
  "properties": {
    "project": {"type": "string"},
    "planId": {"type": "number"},          // camelCase, not test_plan_id
    "suiteId": {"type": "number"},         // camelCase, not test_suite_id
    "testCaseIds": {                       // camelCase, not test_case_ids
      "anyOf": [
        {"type": "string"},                // Can be "123"
        {"type": "array", "items": {"type": "string"}}  // Or ["123", "124"]
      ]
    }
  }
}
```

## Why It Failed Silently
The MCP client returned an error dict with `{'text': 'MCP error -32602: ...'}`, but the code was checking:
```python
if isinstance(result, dict) and result.get("id"):
    # Success
```

Since the error dict has no `id` field, it just continued without raising an exception, making it appear successful.

## Fixes Applied

### 1. Fixed Agent Prompt (line ~915 in studio_graph_autonomous.py)
**Before:**
```python
{{"project": "{project}", "test_plan_id": {test_plan_id}, "test_suite_id": {test_suite_id}, "test_case_ids": [test_case_id]}}
```

**After:**
```python
{{"project": "{project}", "planId": {test_plan_id}, "suiteId": {test_suite_id}, "testCaseIds": "[test_case_id_as_string]"}}

CRITICAL: testCaseIds must be a STRING, not a number! Convert the test case ID to string!
```

### 2. Manual Fix Executed
Ran `fix_test_case_addition.py` which properly added all 5 test cases (1163-1167) to suite 370.

### 3. Verified Results
```bash
Test cases in suite: 5
- Test: User Registration with Email Verification
- Test: User Login with JWT Authentication
- Test: Create New User Profile with Multi-Factor Authentication
- Test: RESTful API CRUD Operations for User Management
- Test: Database Schema and Data Validation
```

## Impact
- **Original Issue**: Test cases created but NOT added to suite (appeared empty in ADO UI)
- **After Fix**: All test cases properly added and visible in Test Plan 370, Suite 370

## Prevention
1. Always check tool schemas using `client.get_tools()` to see exact parameter names and types
2. Validate tool results - if result contains `{'text': 'MCP error ...'}`, treat as failure
3. Add explicit error handling for MCP tool calls
4. Use consistent parameter naming (check if tool uses camelCase or snake_case)

## Testing
Refresh the Azure DevOps Test Plans page - you should now see 5 test cases in suite 370.

---
**Status**: ✅ RESOLVED
**Date**: January 18, 2026
**Fixed By**: Correcting MCP tool parameter names and types
