#!/usr/bin/env python
"""Check test cases via REST API."""

import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("AZURE_DEVOPS_PAT")

headers = {
    "Authorization": f"Basic OnthcHBhdHI6{token}",
    "Content-Type": "application/json"
}

# Check test cases in suite
url = 'https://dev.azure.com/appatr/testingmcp/_apis/test/Plans/369/Suites/370/testcases?api-version=7.1-preview.3'
response = httpx.get(url, headers=headers)

print("=" * 60)
print("TEST CASES IN SUITE 370 (via REST API)")
print("=" * 60)
print(f"\nStatus Code: {response.status_code}")
print(f"\nResponse Text: {response.text}")

if response.status_code == 200 and response.text:
    result = response.json()
    print(f"\nCount: {result.get('count', 0)}")
    print(f"\nTest Cases:")
    print(json.dumps(result, indent=2))
else:
    print(f"Failed to get test cases. Status: {response.status_code}")
