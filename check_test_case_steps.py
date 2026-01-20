"""Check the actual test steps in a created test case."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def check_test_case_details():
    """Get details of a specific test case to verify steps."""
    from src.studio_graph_autonomous import get_ado_client
    
    ado_client = get_ado_client()
    
    # Get test case 1284
    print("Fetching test case 1284...")
    result = await ado_client.get_work_item(work_item_id=1284)
    
    fields = result.get("fields", {})
    
    print("\nTest Case Details:")
    print("="*80)
    print(f"ID: 1284")
    print(f"Title: {fields.get('System.Title', 'N/A')}")
    print(f"Type: {fields.get('System.WorkItemType', 'N/A')}")
    print(f"\nTest Steps:")
    print("-"*80)
    
    steps = fields.get('Microsoft.VSTS.TCM.Steps', '')
    if steps:
        # Parse and display steps
        import html
        steps_text = html.unescape(steps)
        # Remove HTML tags for readability
        import re
        steps_clean = re.sub('<[^<]+?>', '', steps_text)
        print(steps_clean[:1000])
    else:
        print("No steps found")
    
    print("\n" + "="*80)
    print("Linked Work Item:")
    print(f"Tests Work Item ID: {fields.get('Microsoft.VSTS.Common.TestedBy', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(check_test_case_details())
