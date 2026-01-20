"""
Check why test_plan agent is not being called in LangGraph Studio
"""
import asyncio
import logging

# Mock state as if we're right after work_items completes
test_state = {
    "user_query": "Build a wealth management app",
    "project_name": "wealth-management",
    "requirements": "Some requirements here",
    "work_items": {
        "created_ids": [1299, 1300, 1301],
        "description": "Created 3 work items"
    },
    "test_plan": None,
    "test_plan_complete": False,  # This should be FALSE
    "architecture": None,
    "code_artifacts": None
}

# Simulate orchestrator logic
has_requirements = test_state.get("requirements") is not None
has_work_items = test_state.get("work_items") is not None
has_test_plan = test_state.get("test_plan_complete", False)
has_architecture = test_state.get("architecture") is not None
has_code = test_state.get("code_artifacts") is not None

print("="*80)
print("ORCHESTRATOR STATE CHECK")
print("="*80)
print(f"has_requirements: {has_requirements}")
print(f"has_work_items: {has_work_items}")
print(f"has_test_plan: {has_test_plan}")
print(f"has_architecture: {has_architecture}")
print(f"has_code: {has_code}")
print()

# Determine next agent
if not has_requirements:
    next_agent = "requirements"
elif not has_work_items:
    next_agent = "work_items"
elif not has_test_plan:
    next_agent = "test_plan"
elif not has_architecture:
    next_agent = "architecture"
elif not has_code:
    next_agent = "development"
else:
    next_agent = "complete"

print(f"🎯 Next Agent: {next_agent}")
print()

if next_agent == "test_plan":
    print("✅ TEST_PLAN AGENT SHOULD BE CALLED")
else:
    print(f"❌ TEST_PLAN AGENT SKIPPED - going to {next_agent} instead!")
    print()
    print("POSSIBLE CAUSES:")
    print(f"  1. test_plan_complete is True: {test_state.get('test_plan_complete')}")
    print(f"  2. work_items is None: {test_state.get('work_items') is None}")
    print(f"  3. requirements is None: {test_state.get('requirements') is None}")
