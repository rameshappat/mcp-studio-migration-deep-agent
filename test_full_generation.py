"""Clean up old test cases and run full test."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def cleanup_and_test():
    """Clean old test cases and test full flow."""
    from src.studio_graph_autonomous import get_ado_client, test_plan_agent_node, DeepPipelineState
    
    ado_client = get_ado_client()
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    test_plan_id = int(os.getenv("SDLC_TESTPLAN_ID", "369"))
    test_suite_id = int(os.getenv("SDLC_TESTSUITE_ID", "370"))
    
    print("="*80)
    print("STEP 1: Checking existing test cases in suite 370")
    print("="*80)
    
    # List test cases in suite
    result = await ado_client.call_tool('testplan_list_test_cases', {
        'project': project,
        'planid': test_plan_id,
        'suiteid': test_suite_id
    }, timeout=30)
    
    existing_cases = result if isinstance(result, list) else []
    print(f"Found {len(existing_cases)} existing test cases")
    
    if existing_cases:
        print("\nExisting test cases:")
        for tc in existing_cases[:5]:
            print(f"  - {tc.get('testCase', {}).get('id')}: {tc.get('testCase', {}).get('name')}")
        
        if len(existing_cases) > 5:
            print(f"  ... and {len(existing_cases) - 5} more")
    
    print("\n" + "="*80)
    print("STEP 2: Running test plan agent to generate NEW test cases")
    print("="*80)
    
    state: DeepPipelineState = {
        "messages": [],
        "user_query": "Generate test cases for all work items",
        "consecutive_failures": {},
    }
    
    result = await test_plan_agent_node(state)
    
    print("\n" + "="*80)
    print("STEP 3: Results")
    print("="*80)
    print(f"Test cases created: {len(result.get('test_cases', []))}")
    
    if result.get('test_cases'):
        print("\n✅ Newly created test cases:")
        for tc in result['test_cases']:
            print(f"\n  ID {tc['test_case_id']}: {tc['title']}")
            print(f"  → Linked to work item: {tc['work_item_id']}")
    
    if result.get('failed_tool_calls'):
        print(f"\n⚠️  Failed operations: {len(result['failed_tool_calls'])}")


if __name__ == "__main__":
    asyncio.run(cleanup_and_test())
