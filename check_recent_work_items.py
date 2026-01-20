#!/usr/bin/env python3
"""Check the most recent work items created"""
import httpx
import os
from datetime import datetime

ADO_ORG = "appatr"
ADO_PROJECT = "testingmcp"
ADO_TOKEN = os.environ.get("ADO_MCP_AUTH_TOKEN")

headers = {
    "Authorization": f"Basic {ADO_TOKEN}",
    "Content-Type": "application/json"
}

def list_recent_work_items():
    """List the 20 most recent work items"""
    url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/wit/wiql?api-version=7.1"
    
    query = {
        "query": f"SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.CreatedDate] FROM workitems WHERE [System.TeamProject] = '{ADO_PROJECT}' ORDER BY [System.CreatedDate] DESC"
    }
    
    try:
        response = httpx.post(url, json=query, headers=headers, timeout=30)
        response.raise_for_status()
        
        work_items = response.json().get("workItems", [])
        
        if not work_items:
            print("❌ No work items found")
            return
        
        # Get first 20 IDs
        ids = [str(wi["id"]) for wi in work_items[:20]]
        
        # Fetch details
        details_url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/wit/workitems?ids={','.join(ids)}&api-version=7.1"
        details_response = httpx.get(details_url, headers=headers, timeout=30)
        details_response.raise_for_status()
        
        items = details_response.json().get("value", [])
        
        print(f"\n✅ Found {len(items)} most recent work items:\n")
        for item in items:
            fields = item.get("fields", {})
            wi_id = item.get("id")
            wi_type = fields.get("System.WorkItemType", "N/A")
            title = fields.get("System.Title", "N/A")
            state = fields.get("System.State", "N/A")
            created = fields.get("System.CreatedDate", "N/A")
            
            # Parse date
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                created_str = created
            
            print(f"ID: {wi_id} | Type: {wi_type}")
            print(f"  Title: {title}")
            print(f"  State: {state}")
            print(f"  Created: {created_str}")
            print()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    list_recent_work_items()
