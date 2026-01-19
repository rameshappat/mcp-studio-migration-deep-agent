#!/usr/bin/env python3
"""Query the most recent pipeline run thread state to see test cases."""

import os
import sys
import requests

# LangSmith API
api_key = os.getenv("LANGSMITH_API_KEY")
if not api_key:
    print("❌ LANGSMITH_API_KEY not set")
    sys.exit(1)

# Get most recent run
url = "https://api.smith.langchain.com/runs"
params = {
    "project": "sdlc-autonomous-pipeline",
    "limit": 5,
    "order": "-start_time"
}
headers = {
    "x-api-key": api_key
}

response = requests.get(url, params=params, headers=headers)
if response.status_code != 200:
    print(f"❌ Error: {response.status_code} - {response.text}")
    sys.exit(1)

runs = response.json()
print(f"\n=== Last {len(runs)} Pipeline Runs ===\n")

for i, run in enumerate(runs, 1):
    print(f"{i}. Run ID: {run['id']}")
    print(f"   Started: {run.get('start_time', 'Unknown')}")
    print(f"   Status: {run.get('status', 'Unknown')}")
    print(f"   Name: {run.get('name', 'Unknown')}")
    
    # Check outputs
    outputs = run.get('outputs', {})
    test_cases = outputs.get('test_cases', [])
    print(f"   Test Cases: {len(test_cases)}")
    
    if test_cases:
        for tc in test_cases[:3]:
            print(f"      • {tc.get('test_case_id')}: {tc.get('title', 'No title')}")
    else:
        print("      ❌ NO TEST CASES")
    
    print()
