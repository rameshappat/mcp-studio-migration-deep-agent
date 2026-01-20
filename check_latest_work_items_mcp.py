#!/usr/bin/env python3
"""Check work items created today using MCP"""
import asyncio
from src.mcp_client.azure_devops_client import AzureDevOpsMCPClient

async def main():
    client = AzureDevOpsMCPClient()
    
    try:
        # Query for work items created today
        wiql = """
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.CreatedDate]
        FROM workitems
        WHERE [System.TeamProject] = 'testingmcp'
        ORDER BY [System.CreatedDate] DESC
        """
        
        print("\n🔍 Checking recent work items...")
        result = await client.query_wiql(wiql)
        
        work_items = result.get("workItems", [])
        print(f"\n✅ Found {len(work_items)} work items\n")
        
        # Get the first 15 work items
        if work_items:
            ids = [wi["id"] for wi in work_items[:15]]
            
            for wi_id in ids:
                wi_result = await client.get_work_item(wi_id)
                fields = wi_result.get("fields", {})
                
                print(f"\n{'='*60}")
                print(f"ID: {wi_id}")
                print(f"Type: {fields.get('System.WorkItemType', 'N/A')}")
                print(f"Title: {fields.get('System.Title', 'N/A')}")
                print(f"Description: {fields.get('System.Description', 'N/A')[:200] if fields.get('System.Description') else 'N/A'}...")
                print(f"Created: {fields.get('System.CreatedDate', 'N/A')}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
