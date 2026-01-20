#!/usr/bin/env python3
"""
Find the root cause of why test cases aren't being generated
"""

# The problem is that work_items_agent creates work items via Deep Agent tool calls,
# but then tries to extract IDs by parsing URLs from the output string.
#
# ISSUE: If the Deep Agent doesn't return URLs in its output (which it might not),
# then created_ids will be empty, and test_plan_agent will skip test case creation.
#
# SOLUTION: Modify work_items_agent_node to extract work item IDs directly from
# the tool_calls results, not from parsing output text.

print("""
================================================================================
ROOT CAUSE ANALYSIS: Why Test Cases Aren't Being Generated
================================================================================

PROBLEM:
--------
The work_items_agent_node tries to extract work item IDs by parsing URLs from 
the Deep Agent's output text using this regex:

    id_pattern = r'/edit/(\\d+)'
    matches = re.findall(id_pattern, output)

This assumes the Deep Agent will return URLs like:
    https://dev.azure.com/appatr/testingmcp/_workitems/edit/1224

However, the Deep Agent might not always include these URLs in its output!

EVIDENCE:
---------
From the logs you saw:
- has_work_items: True  ← Work items agent completed
- has_test_plan: True   ← Test plan agent completed  
- But NO new test cases were created!

This means:
1. Deep Agent called ado_wit_create_work_item tools successfully
2. Work items were created in ADO
3. But created_ids was empty (no URLs found in output)
4. Test plan agent ran but had no work items to process

SOLUTION:
---------
Instead of parsing URLs from output text, we should extract work item IDs 
directly from the tool_calls results. Each successful ado_wit_create_work_item
call returns the work item ID in the result.

FIX LOCATION:
-------------
File: src/studio_graph_autonomous.py
Lines: ~890-895

CURRENT CODE:
```python
# Parse work item IDs from the agent output (URLs contain IDs)
id_pattern = r'/edit/(\\d+)'
matches = re.findall(id_pattern, output)
created_ids = [int(id_str) for id_str in matches]
```

SHOULD BE:
```python
# Extract work item IDs from successful tool call results
created_ids = []
for tool_call in tool_calls:
    if tool_call.get("tool") == "ado_wit_create_work_item":
        result = tool_call.get("result", {})
        # Check if this was a successful creation
        if isinstance(result, dict) and "id" in result:
            created_ids.append(result["id"])
        # Also try to parse from text if available
        elif isinstance(result, dict) and "text" in result:
            text = result["text"]
            if "id" in text.lower() and "error" not in text.lower():
                # Try to extract ID from text
                import re
                id_match = re.search(r'"id":\\s*(\\d+)', text)
                if id_match:
                    created_ids.append(int(id_match.group(1)))
```

ACTION NEEDED:
--------------
Update the work_items_agent_node to extract IDs from tool_calls instead of 
parsing output text. This will ensure test_plan_agent receives the work item 
IDs and can create test cases.

================================================================================
""")
