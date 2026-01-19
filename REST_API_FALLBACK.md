# REST API Fallback for Test Plan Operations

## Problem
MCP tool calls to Azure DevOps were timing out or hanging indefinitely, preventing test cases from being created during pipeline execution.

## Solution
Added comprehensive REST API fallback for all test plan operations in `src/mcp_client/ado_client.py`:

### Features Added

1. **Automatic Timeout Detection** (60 seconds default)
   - All MCP tool calls now have timeout protection
   - Prevents indefinite hangs

2. **Automatic REST Fallback**
   - When MCP times out or fails, automatically tries REST API
   - Applies to all `testplan_*` operations

3. **Supported Operations**
   - `testplan_create_test_case` → REST API work item creation
   - `testplan_add_test_cases_to_suite` → REST API suite management
   - `testplan_list_test_cases` → REST API query
   - `testplan_create_test_suite` → REST API suite creation

### Setup Required

**For REST fallback to work, you MUST set a PAT (Personal Access Token):**

```bash
export AZURE_DEVOPS_PAT="your_pat_token_here"
```

Or use one of these alternative names:
- `AZURE_DEVOPS_EXT_PAT`
- `ADO_MCP_AUTH_TOKEN`
- `AZURE_DEVOPS_TOKEN`

**To create a PAT:**
1. Go to https://dev.azure.com/{your_org}/_usersSettings/tokens
2. Click "New Token"
3. Give it these scopes:
   - **Work Items**: Read, Write & Manage
   - **Test Management**: Read & Write
4. Copy the token and set it in your environment

### How It Works

```python
# Example: MCP times out, automatically falls back to REST
result = await client.call_tool('testplan_create_test_case', {
    'project': 'testingmcp',
    'title': 'Test: My Test Case',
    'steps': '1. Action|Expected\\n2. Action|Expected'
}, timeout=60)

# If MCP times out after 60s:
# 1. Logs: "❌ TIMEOUT: testplan_create_test_case"
# 2. Logs: "🔄 Attempting REST API fallback"
# 3. Calls _rest_create_test_case() via REST API
# 4. Returns result or error
```

### Error Handling

All REST operations return consistent error format:
```json
{
  "text": "Error description",
  "error": "error_code"
}
```

Error codes:
- `timeout` - MCP timed out
- `no_pat` - No PAT token available for REST
- `not_implemented` - No REST fallback for this operation
- `rest_failed` - REST API call failed
- `http_error` - HTTP error from Azure DevOps
- `missing_fields` - Required parameters missing

### Code Changes

**Modified Files:**
- `src/mcp_client/ado_client.py`:
  - Updated `call_tool()` with timeout and exception handling
  - Added `_rest_fallback()` router method
  - Added `_rest_create_test_case()`
  - Added `_rest_add_test_cases_to_suite()`
  - Added `_rest_list_test_cases()`
  - Added `_rest_create_test_suite()`
  - Added `_format_test_steps()` for ADO XML format

### Testing

```bash
# Test REST fallback directly (requires PAT)
python test_rest_fallback.py

# Test MCP timeout -> REST fallback
python test_mcp_timeout_fallback.py
```

### Pipeline Impact

The autonomous SDLC pipeline will now:
1. Try MCP first (60s timeout)
2. Automatically fallback to REST on timeout/error
3. Log all attempts with clear status
4. Continue pipeline execution instead of failing

### Limitations

- **Interactive auth mode**: Cannot use REST fallback (no PAT available)
- **Solution**: Set `AZURE_DEVOPS_PAT` to enable REST fallback
- **Workaround**: Change `auth_type` to `"envvar"` when PAT is set

### Next Steps

To fully enable REST fallback in your environment:

```bash
# 1. Create PAT in Azure DevOps
# 2. Export it
export AZURE_DEVOPS_PAT="your_pat_here"

# 3. Run pipeline
python run_autonomous_pipeline.py
```

The pipeline will now automatically recover from MCP timeouts!
