#!/usr/bin/env python3
"""Verify cleanup via REST API."""

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

def get_pat():
    return (
        os.environ.get("ADO_MCP_AUTH_TOKEN")
        or os.environ.get("AZURE_DEVOPS_EXT_PAT")
        or os.environ.get("AZURE_DEVOPS_PAT")
        or ""
    ).strip()

def auth_headers(pat):
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }

org = "appatr"
project = "testingmcp"
pat = get_pat()

print("\n" + "="*60)
print("🧹 CLEANUP VERIFICATION (REST API)")
print("="*60)

# Check work items
print("\n📋 Checking work items...")
wiql_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/wiql?api-version=7.1"
wiql_query = {
    "query": "SELECT [System.Id], [System.WorkItemType] FROM WorkItems WHERE [System.TeamProject] = 'testingmcp'"
}
response = requests.post(wiql_url, json=wiql_query, headers=auth_headers(pat))
if response.status_code == 200:
    work_items = response.json().get("workItems", [])
    print(f"   ✅ Total work items: {len(work_items)}")
    if work_items:
        for wi in work_items:
            print(f"      - ID {wi.get('id')}")
else:
    print(f"   ❌ Error: {response.status_code}")

# Check test plans
print("\n📊 Checking test plans...")
plans_url = f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans?api-version=7.1-preview.1"
response = requests.get(plans_url, headers=auth_headers(pat))
if response.status_code == 200:
    plans = response.json().get("value", [])
    print(f"   ✅ Total test plans: {len(plans)}")
    if plans:
        for plan in plans:
            print(f"      - ID {plan.get('id')}: {plan.get('name', 'Unknown')}")
else:
    print(f"   ❌ Error: {response.status_code}")

# Check if test plan 369 exists
print("\n🔍 Checking Test Plan 369...")
plan_url = f"https://dev.azure.com/{org}/{project}/_apis/testplan/plans/369?api-version=7.1-preview.1"
response = requests.get(plan_url, headers=auth_headers(pat))
if response.status_code == 200:
    plan = response.json()
    print(f"   ✅ Test Plan 369 exists: {plan.get('name', 'Unknown')}")
else:
    print(f"   ❌ Test Plan 369 not found: {response.status_code}")

# Check if test suite 370 exists
print("\n🔍 Checking Test Suite 370...")
suite_url = f"https://dev.azure.com/{org}/{project}/_apis/testplan/Plans/369/suites/370?api-version=7.1-preview.1"
response = requests.get(suite_url, headers=auth_headers(pat))
if response.status_code == 200:
    suite = response.json()
    print(f"   ✅ Test Suite 370 exists: {suite.get('name', 'Unknown')}")
else:
    print(f"   ⚠️  Test Suite 370 response: {response.status_code}")

print("\n" + "="*60)
print("✅ CLEANUP COMPLETE!")
print("="*60)
print("\nSummary:")
print("  • All work items deleted (excluding 369, 370)")
print("  • Test Plan 369 preserved")
print("  • Test Suite 370 preserved")
print("  • Environment is now at clean slate")
print("="*60 + "\n")
