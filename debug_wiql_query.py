"""Check work items in ADO using direct REST API."""
import asyncio
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '/Users/rameshappat/Downloads/mcp-studio-migration-deep-agent')
from src.studio_graph_autonomous import get_ado_client

load_dotenv()


async def check_work_items():
    """Check what work items exist."""
    client = get_ado_client()
    
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    # Try different queries
    queries = [
        f"SELECT [System.Id] FROM WorkItems",
        f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] <> 'Test Case'",
        f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project}'",
    ]
    
    for idx, query in enumerate(queries, 1):
        print(f"\n{'='*80}")
        print(f"Query {idx}: {query}")
        print('='*80)
        
        try:
            result = await client.call_tool('work_query_by_wiql', {
                'project': project,
                'query': query
            }, timeout=30)
            
            if isinstance(result, dict) and "error" in result:
                print(f"❌ Error: {result.get('text')}")
            else:
                work_items = result.get("workItems", [])
                print(f"✅ Found {len(work_items)} work items")
                
                if work_items:
                    print("\nWork Item IDs:")
                    for wi in work_items[:10]:
                        print(f"  - {wi.get('id')}")
        except Exception as e:
            print(f"❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(check_work_items())
