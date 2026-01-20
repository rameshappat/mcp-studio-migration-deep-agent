#!/usr/bin/env python3
"""Debug the pipeline state to see what's happening"""
import asyncio
import sys
sys.path.insert(0, '/Users/rameshappat/Downloads/mcp-studio-migration-deep-agent')

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def main():
    client = AzureDevOpsMCPClient()
    
    try:
        # Get all work items
        print("\n🔍 Checking all work items in project...")
        result = await client.call_tool('wit_query_wiql', {
            'project': 'testingmcp',
            'wiql': 'SELECT [System.Id], [System.Title], [System.WorkItemType], [System.CreatedDate] FROM workitems WHERE [System.TeamProject] = @project ORDER BY [System.CreatedDate] DESC'
        })
        
        print(f"\nResult type: {type(result)}")
        
        if isinstance(result, dict):
            work_items = result.get('workItems', [])
            print(f"✅ Found {len(work_items)} work items\n")
            
            # Get details for the first 10
            for i, wi in enumerate(work_items[:10]):
                wi_id = wi.get('id')
                print(f"\n{'='*60}")
                print(f"Work Item #{i+1}: ID {wi_id}")
                
                # Get full details
                wi_details = await client.call_tool('wit_get_work_item', {
                    'id': wi_id,
                    'project': 'testingmcp'
                })
                
                if isinstance(wi_details, dict):
                    fields = wi_details.get('fields', {})
                    print(f"  Type: {fields.get('System.WorkItemType', 'N/A')}")
                    print(f"  Title: {fields.get('System.Title', 'N/A')}")
                    print(f"  State: {fields.get('System.State', 'N/A')}")
                    print(f"  Created: {fields.get('System.CreatedDate', 'N/A')}")
                    
                    desc = fields.get('System.Description', '')
                    if desc:
                        print(f"  Description: {desc[:150]}...")
        
        # Check test suite 370
        print("\n\n" + "="*60)
        print("🧪 Checking Test Suite 370...")
        test_result = await client.call_tool('testplan_list_test_cases', {
            'project': 'testingmcp',
            'planid': 369,
            'suiteid': 370
        })
        
        if isinstance(test_result, list):
            print(f"✅ Found {len(test_result)} test cases in suite 370")
            for tc in test_result[:5]:
                if isinstance(tc, dict):
                    wi = tc.get('workItem', {})
                    print(f"  - Test Case {wi.get('id')}: {wi.get('name', 'N/A')}")
        else:
            print(f"⚠️  No test cases found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
