#!/usr/bin/env python
"""Update test case names to be more contextual based on work items."""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def update_test_cases():
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    await client.connect()
    
    # Mapping of work items to test cases
    mapping = [
        (1215, 1216),
        (1214, 1217),
        (1213, 1218),
        (1212, 1219),
        (1211, 1220),
        (1210, 1221),
        (1209, 1222),
        (1208, 1223),
    ]
    
    print("🔄 Updating test case names with contextual information...\n")
    
    for wi_id, tc_id in mapping:
        try:
            # Get work item details
            wi_details = await client.get_work_item(work_item_id=wi_id)
            fields = wi_details.get("fields", {})
            
            title = fields.get("System.Title", f"Work Item {wi_id}")
            wi_type = fields.get("System.WorkItemType", "")
            description = fields.get("System.Description", "")
            acceptance_criteria = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
            
            print(f"📝 WI-{wi_id} ({wi_type}): {title}")
            
            # Create contextual test case title and steps
            test_title = f"Verify {wi_type}: {title}"
            
            # Build test steps from acceptance criteria or description
            test_steps = ""
            if acceptance_criteria:
                test_steps = f"1. Review requirement: {title}\n2. Verify acceptance criteria:\n{acceptance_criteria[:200]}\n3. Validate all functionality meets requirements"
            elif description:
                test_steps = f"1. Review requirement: {title}\n2. Test scenario:\n{description[:200]}\n3. Verify expected outcomes match requirements"
            else:
                test_steps = f"1. Review requirement: {title}\n2. Execute test scenario for {wi_type.lower()}\n3. Verify all functionality works as expected"
            
            # Update test case
            print(f"   Updating TC-{tc_id}...")
            result = await client.call_tool('wit_update_work_item', {
                'project': 'testingmcp',
                'id': tc_id,
                'title': test_title
            })
            
            # Also update the steps field
            result2 = await client.call_tool('testplan_update_test_case_steps', {
                'id': tc_id,
                'steps': test_steps
            })
            
            print(f"   ✅ Updated: {test_title[:70]}...\n")
            
        except Exception as e:
            print(f"   ❌ Error updating TC-{tc_id}: {e}\n")
    
    print("=" * 60)
    print("✅ Test case names updated with context!")
    print("=" * 60)
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(update_test_cases())
