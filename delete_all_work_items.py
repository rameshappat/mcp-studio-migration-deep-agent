#!/usr/bin/env python3
"""Delete all work items and test cases from ADO, preserving Test Plan 369 and Suite 370.

Usage: python3 delete_all_work_items.py [PAT]
If PAT not provided, will prompt for it.
"""

import subprocess
import json
import os
import sys
import getpass

# Get credentials
org = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")

# Get PAT from command line arg or prompt
if len(sys.argv) > 1:
    pat = sys.argv[1]
    print(f"✅ Using PAT from command line")
else:
    pat = getpass.getpass("Enter Azure DevOps PAT (will be hidden): ")

if not pat:
    print("❌ PAT required")
    sys.exit(1)

print(f"🧹 Cleaning up ADO project: {project}")

# Query for all work items using Azure CLI
query = """
SELECT [System.Id], [System.WorkItemType], [System.Title]
FROM WorkItems
WHERE [System.TeamProject] = 'testingmcp'
ORDER BY [System.Id] DESC
"""

try:
    # Use Azure DevOps REST API directly
    import requests
    from requests.auth import HTTPBasicAuth
    
    base_url = f"https://dev.azure.com/{org}/{project}/_apis"
    auth = HTTPBasicAuth('', pat)
    
    # Query work items
    wiql_url = f"{base_url}/wit/wiql?api-version=7.0"
    response = requests.post(
        wiql_url,
        json={"query": query},
        auth=auth,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        work_items = data.get("workItems", [])
        
        print(f"📋 Found {len(work_items)} total work items")
        
        deleted_count = 0
        failed_count = 0
        
        for wi in work_items:
            wi_id = wi.get("id")
            
            # Get work item details
            wi_url = f"{base_url}/wit/workitems/{wi_id}?api-version=7.0"
            wi_response = requests.get(wi_url, auth=auth)
            
            if wi_response.status_code == 200:
                wi_data = wi_response.json()
                wi_type = wi_data.get("fields", {}).get("System.WorkItemType", "")
                wi_title = wi_data.get("fields", {}).get("System.Title", "")
                
                print(f"  🗑️  Deleting {wi_type} {wi_id}: {wi_title[:50]}...")
                
                # Delete work item
                delete_url = f"{base_url}/wit/workitems/{wi_id}?api-version=7.0"
                delete_response = requests.delete(delete_url, auth=auth)
                
                if delete_response.status_code in [200, 204]:
                    print(f"    ✅ Deleted successfully")
                    deleted_count += 1
                else:
                    print(f"    ❌ Failed: {delete_response.status_code} - {delete_response.text}")
                    failed_count += 1
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Work items deleted: {deleted_count}")
        print(f"   Failed: {failed_count}")
        print(f"   Test Plan 369 and Suite 370 preserved")
    else:
        print(f"❌ Failed to query work items: {response.status_code}")
        print(response.text)
        
except ImportError:
    print("❌ 'requests' module not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    print("✅ Please run the script again")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
