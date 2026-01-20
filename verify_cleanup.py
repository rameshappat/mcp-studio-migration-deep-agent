#!/usr/bin/env python3
"""Verify that test plan 369 and suite 370 are still present after cleanup."""

import os
import sys
import httpx
import base64

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env")
except Exception:
    pass


def main():
    pat = os.environ.get("ADO_MCP_AUTH_TOKEN", "").strip()
    if not pat:
        print("Missing ADO_MCP_AUTH_TOKEN")
        return 1
    
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json"
    }
    
    org = "appatr"
    project = "testingmcp"
    
    with httpx.Client(headers=headers, timeout=30.0) as client:
        # List all test plans
        print("Checking test plans...")
        resp = client.get(f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans?api-version=7.1-preview.1")
        if resp.status_code == 200:
            plans = resp.json().get("value", [])
            print(f"Found {len(plans)} test plan(s):")
            for plan in plans:
                print(f'  - Plan ID {plan["id"]}: {plan.get("name", "N/A")}')
        else:
            print(f"Failed to list test plans: {resp.status_code}")
        
        print()
        
        # Check test plan 369
        resp = client.get(f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans/369?api-version=7.1-preview.1")
        if resp.status_code == 200:
            plan = resp.json()
            print(f'✓ Test Plan 369 exists: {plan.get("name", "N/A")}')
        else:
            print(f"✗ Test Plan 369 not found: {resp.status_code}")
        
        # Check suite 370
        resp = client.get(f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans/369/suites/370?api-version=7.1-preview.1")
        if resp.status_code == 200:
            suite = resp.json()
            print(f'✓ Test Suite 370 exists: {suite.get("name", "N/A")}')
        else:
            print(f"✗ Test Suite 370 not found: {resp.status_code}")
        
        print()
        
        # Check for any remaining work items
        from scripts.delete_all_work_items import _wiql_url, AdoTarget, _query_work_item_ids
        target = AdoTarget(org=org, project=project)
        ids = _query_work_item_ids(client, target)
        print(f"Total work items remaining: {len(ids)}")
        if ids:
            print(f"Work item IDs: {ids}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
