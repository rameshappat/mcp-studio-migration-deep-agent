#!/usr/bin/env python3
"""Direct REST API check of ADO test cases - bypassing MCP."""

import os
import requests
from requests.auth import HTTPBasicAuth

org = os.getenv("AZURE_DEVOPS_ORG", "appatr")
project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
pat = os.getenv("AZURE_DEVOPS_PAT", "")

test_plan_id = 369
test_suite_id = 370

if not pat:
    print("❌ AZURE_DEVOPS_PAT not set")
    exit(1)

base_url = f"https://dev.azure.com/{org}/{project}"

# Get test cases in suite
url = f"{base_url}/_apis/testplan/Plans/{test_plan_id}/Suites/{test_suite_id}/TestCase?api-version=7.1-preview.3"

print(f"\n=== Checking ADO Direct (REST API) ===")
print(f"Organization: {org}")
print(f"Project: {project}")
print(f"Test Plan: {test_plan_id}")
print(f"Test Suite: {test_suite_id}")
print(f"\nURL: {url}\n")

auth = HTTPBasicAuth('', pat)
response = requests.get(url, auth=auth)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    test_cases = data.get('value', [])
    print(f"\n✅ Test Cases Found: {len(test_cases)}\n")
    
    if test_cases:
        for tc in test_cases:
            wi = tc.get('workItem', {})
            print(f"  • ID {wi.get('id')}: {wi.get('name', 'No name')}")
    else:
        print("❌ NO TEST CASES IN THIS SUITE")
else:
    print(f"❌ Error: {response.text}")
