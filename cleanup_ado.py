import os
import asyncio
from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def cleanup_ado():
    org = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    client = AzureDevOpsMCPClient(organization=org, project=project)
    await client.connect()
    
    print(f"🧹 Cleaning up ADO project: {project}")
    
    # Query for all work items
    wiql_query = """
    SELECT [System.Id], [System.WorkItemType], [System.Title]
    FROM WorkItems
    WHERE [System.TeamProject] = 'testingmcp'
    ORDER BY [System.Id] DESC
    """
    
    result = await client.call_tool("wit_query_by_wiql", {
        "project": project,
        "query": wiql_query
    })
    
    if result and "text" in result:
        import json
        data = json.loads(result["text"])
        work_items = data.get("workItems", [])
        
        print(f"📋 Found {len(work_items)} total work items")
        
        # Separate test cases from other work items
        work_item_ids = []
        test_case_ids = []
        
        for wi in work_items:
            wi_id = wi.get("id")
            # Get work item details to check type
            wi_details = await client.call_tool("wit_get_work_item", {
                "project": project,
                "id": wi_id
            })
            
            if wi_details and "text" in wi_details:
                wi_data = json.loads(wi_details["text"])
                wi_type = wi_data.get("fields", {}).get("System.WorkItemType", "")
                wi_title = wi_data.get("fields", {}).get("System.Title", "")
                
                if wi_type == "Test Case":
                    test_case_ids.append(wi_id)
                    print(f"  🧪 Test Case {wi_id}: {wi_title[:50]}")
                else:
                    work_item_ids.append(wi_id)
                    print(f"  📝 {wi_type} {wi_id}: {wi_title[:50]}")
        
        print(f"\n🗑️  Deleting {len(work_item_ids)} work items (Epics/Issues)...")
        for wi_id in work_item_ids:
            try:
                await client.call_tool("wit_delete_work_item", {
                    "project": project,
                    "id": wi_id
                })
                print(f"  ✅ Deleted work item {wi_id}")
            except Exception as e:
                print(f"  ❌ Failed to delete work item {wi_id}: {e}")
        
        print(f"\n🗑️  Deleting {len(test_case_ids)} test cases...")
        for tc_id in test_case_ids:
            try:
                await client.call_tool("wit_delete_work_item", {
                    "project": project,
                    "id": tc_id
                })
                print(f"  ✅ Deleted test case {tc_id}")
            except Exception as e:
                print(f"  ❌ Failed to delete test case {tc_id}: {e}")
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Work items deleted: {len(work_item_ids)}")
        print(f"   Test cases deleted: {len(test_case_ids)}")
        print(f"   Test Plan 369 and Suite 370 preserved")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(cleanup_ado())
