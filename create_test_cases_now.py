#!/usr/bin/env python
"""Manually create test cases for existing work items."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def create_test_cases():
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    await client.connect()
    
    test_plan_id = 369
    test_suite_id = 370
    project = 'testingmcp'
    
    # Get current work items (excluding test plan/suite)
    work_item_ids = [1215, 1214, 1213, 1212, 1211, 1210, 1209, 1208]
    
    print(f"\n🔧 Creating test cases for {len(work_item_ids)} work items...")
    print(f"   Test Plan: {test_plan_id}")
    print(f"   Test Suite: {test_suite_id}")
    
    created_cases = []
    failed_cases = []
    
    for wi_id in work_item_ids:
        try:
            # Get work item details
            wi_details = await client.get_work_item(work_item_id=wi_id)
            fields = wi_details.get("fields", {})
            
            title = fields.get("System.Title", f"Work Item {wi_id}")
            description = fields.get("System.Description", "")
            wi_type = fields.get("System.WorkItemType", "")
            
            print(f"\n📝 Processing WI-{wi_id}: {wi_type} - {title[:50]}...")
            
            # Create test case title
            test_title = f"Test: {title}"
            
            # Create simple test steps from description
            steps = f"1. Verify implementation of: {title}\n2. Test all acceptance criteria\n3. Validate expected outcomes"
            if description:
                steps = f"1. Review requirement: {description[:100]}\n2. Execute test scenario\n3. Verify results"
            
            # Create test case
            print(f"   Creating test case...")
            result = await client.call_tool('testplan_create_test_case', {
                'project': project,
                'title': test_title,
                'steps': steps,
                'priority': 2
            })
            
            if isinstance(result, dict) and "error" not in result:
                test_case_id = result.get("id")
                if test_case_id:
                    print(f"   ✅ Created test case: {test_case_id}")
                    
                    # Add to suite
                    print(f"   Adding to suite {test_suite_id}...")
                    result2 = await client.call_tool('testplan_add_test_cases_to_suite', {
                        'project': project,
                        'planId': test_plan_id,
                        'suiteId': test_suite_id,
                        'testCaseIds': str(test_case_id)
                    })
                    
                    if isinstance(result2, dict) and "error" in result2:
                        print(f"   ⚠️  Failed to add to suite: {result2.get('text', 'Unknown error')[:100]}")
                        failed_cases.append((wi_id, "Failed to add to suite"))
                    else:
                        print(f"   ✅ Added to suite")
                        created_cases.append((wi_id, test_case_id))
                else:
                    print(f"   ❌ No test case ID returned")
                    failed_cases.append((wi_id, "No ID returned"))
            else:
                error_msg = result.get("text", str(result))[:100] if isinstance(result, dict) else str(result)[:100]
                print(f"   ❌ Failed to create test case: {error_msg}")
                failed_cases.append((wi_id, error_msg))
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            failed_cases.append((wi_id, str(e)))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully created: {len(created_cases)} test cases")
    if created_cases:
        for wi_id, tc_id in created_cases:
            print(f"   WI-{wi_id} → Test Case {tc_id}")
    
    if failed_cases:
        print(f"\n❌ Failed: {len(failed_cases)} test cases")
        for wi_id, error in failed_cases:
            print(f"   WI-{wi_id}: {error[:80]}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(create_test_cases())
