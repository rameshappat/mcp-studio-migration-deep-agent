#!/usr/bin/env python3
"""Test script to create test cases from work items and add to suite.

This tests the test case creation logic separately before incorporating into main pipeline.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp_client.ado_client import AzureDevOpsMCPClient
from dotenv import load_dotenv

load_dotenv()


async def test_create_test_cases():
    """Test creating test cases from work items and adding to suite."""
    
    org = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    test_plan_id = int(os.getenv("SDLC_TESTPLAN_ID", "369"))
    test_suite_id = int(os.getenv("SDLC_TESTSUITE_ID", "370"))
    
    # Test with the work items we just created: 973, 974, 975
    work_item_ids_to_test = [973, 974, 975]
    
    print(f"🧪 Testing test case creation")
    print(f"   Organization: {org}")
    print(f"   Project: {project}")
    print(f"   Test Plan ID: {test_plan_id}")
    print(f"   Test Suite ID: {test_suite_id}")
    print(f"   Work Items: {work_item_ids_to_test}")
    print()
    
    ado_client = AzureDevOpsMCPClient(
        organization=org,
        project=project,
    )
    
    print(f"📋 Processing {len(work_item_ids_to_test)} work items...")
    print()
    created_cases = []
    
    # Create test cases for each work item
    for idx, wi_id in enumerate(work_item_ids_to_test, 1):
        print(f"[{idx}] Processing work item {wi_id}...")
        
        # Get work item details
        wi_details = await ado_client.get_work_item(work_item_id=wi_id)
        
        title = wi_details.get("fields", {}).get("System.Title", "Untitled Test Case")
        description = wi_details.get("fields", {}).get("System.Description", "")
        
        print(f"    Title: {title}")
        
        # Create test case
        test_case_title = f"Test: {title}"
        test_steps = f"""<steps>
<step><parameterizedString>Verify: {title}</parameterizedString><parameterizedString>Test passes</parameterizedString><description>{description}</description></step>
</steps>"""
        
        try:
            result = await ado_client.create_test_case(
                title=test_case_title,
                steps=test_steps,
                project=project
            )
            test_case_id = result.get("id")
            print(f"    ✅ Created test case {test_case_id}")
            
            # Add test case to suite
            try:
                await ado_client.add_test_cases_to_suite(
                    project=project,
                    plan_id=test_plan_id,
                    suite_id=test_suite_id,
                    test_case_ids=[str(test_case_id)]
                )
                print(f"    ✅ Added test case {test_case_id} to suite {test_suite_id}")
                created_cases.append({
                    "work_item_id": wi_id,
                    "test_case_id": test_case_id,
                    "title": test_case_title,
                    "result": "success"
                })
            except Exception as suite_error:
                print(f"    ❌ Failed to add to suite: {suite_error}")
                created_cases.append({
                    "work_item_id": wi_id,
                    "test_case_id": test_case_id,
                    "error": str(suite_error),
                    "result": "partial"
                })
        except Exception as e:
            print(f"    ❌ Failed to create test case: {e}")
            created_cases.append({
                "work_item_id": wi_id,
                "error": str(e),
                "result": "error"
            })
        
        print()
    
    # Summary
    success_count = len([c for c in created_cases if c.get("result") == "success"])
    error_count = len([c for c in created_cases if c.get("result") == "error"])
    partial_count = len([c for c in created_cases if c.get("result") == "partial"])
    
    print("=" * 60)
    print("📊 Summary:")
    print(f"   ✅ Success: {success_count}")
    print(f"   ⚠️  Partial: {partial_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📝 Total: {len(created_cases)}")
    print()
    
    if success_count > 0:
        print(f"🎉 Test cases created and added to plan {test_plan_id}, suite {test_suite_id}")
        print(f"   View in ADO: https://dev.azure.com/{org}/{project}/_testPlans/execute?planId={test_plan_id}&suiteId={test_suite_id}")
    else:
        print("❌ No test cases were successfully created and added to suite")
    
    return created_cases


if __name__ == "__main__":
    result = asyncio.run(test_create_test_cases())
