#!/usr/bin/env python3
"""Create sample work items for testing."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp_client.ado_client import AzureDevOpsMCPClient
from dotenv import load_dotenv

load_dotenv()


async def create_sample_work_items():
    """Create 3 sample work items for testing."""
    
    org = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    print(f"🔨 Creating sample work items in {org}/{project}")
    print()
    
    ado_client = AzureDevOpsMCPClient(
        organization=org,
        project=project,
    )
    
    work_items = [
        {
            "title": "User Authentication API",
            "description": "Implement REST API endpoint for user authentication with OAuth 2.0"
        },
        {
            "title": "Todo CRUD Operations",
            "description": "Create endpoints for creating, reading, updating, and deleting todo items"
        },
        {
            "title": "Database Schema Design",
            "description": "Design and implement database schema for user and todo tables"
        }
    ]
    
    created_ids = []
    
    for idx, item in enumerate(work_items, 1):
        print(f"[{idx}] Creating: {item['title']}")
        try:
            result = await ado_client.create_work_item(
                project=project,
                work_item_type="Issue",
                title=item["title"],
                description=item["description"]
            )
            print(f"    Response: {result}")
            wi_id = result.get("id") or result.get("workItemId")
            created_ids.append(wi_id)
            print(f"    ✅ Created work item {wi_id}")
        except Exception as e:
            print(f"    ❌ Failed: {e}")
        print()
    
    print("=" * 60)
    print(f"📊 Created {len(created_ids)} work items: {created_ids}")
    print()
    print("✅ Ready to test test case creation!")
    print("   Run: python scripts/test_create_test_cases.py")
    
    return created_ids


if __name__ == "__main__":
    asyncio.run(create_sample_work_items())
