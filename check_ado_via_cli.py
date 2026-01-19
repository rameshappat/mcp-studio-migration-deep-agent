#!/usr/bin/env python3
"""Check ADO via Azure CLI since we don't have PAT."""

import subprocess
import json
import sys

org = "appatr"
project = "testingmcp"
plan_id = 369
suite_id = 370

print(f"\n=== Checking ADO State via Azure CLI ===")
print(f"Organization: {org}")
print(f"Project: {project}")
print(f"Plan: {plan_id}, Suite: {suite_id}\n")

# Try using az devops CLI
try:
    # Configure org
    subprocess.run(["az", "devops", "configure", "-d", f"organization=https://dev.azure.com/{org}"], 
                   check=False, capture_output=True)
    
    # Get test cases
    result = subprocess.run([
        "az", "devops", "invoke",
        "--area", "testplan",
        "--resource", "test-case",
        "--route-parameters", f"project={project}", f"planId={plan_id}", f"suiteId={suite_id}",
        "--api-version", "7.1-preview.3",
        "--org", f"https://dev.azure.com/{org}"
    ], capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        cases = data.get('value', [])
        print(f"✅ Found {len(cases)} test cases in suite {suite_id}:\n")
        
        if cases:
            for tc in cases:
                wi = tc.get('workItem', {})
                print(f"  • ID {wi.get('id')}: {wi.get('name', 'No name')}")
        else:
            print("❌ NO TEST CASES IN SUITE")
    else:
        print(f"❌ Azure CLI error: {result.stderr}")
        print("\nTrying alternate method...")
        
        # Try work item query instead
        result2 = subprocess.run([
            "az", "boards", "query",
            "--wiql", f"SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'Test Case' AND [System.AreaPath] = '{project}'",
            "--org", f"https://dev.azure.com/{org}",
            "--project", project
        ], capture_output=True, text=True, timeout=30)
        
        if result2.returncode == 0:
            data = json.loads(result2.stdout)
            print(f"\nTotal Test Case work items in project: {len(data)}")
            for item in data[:10]:
                print(f"  • ID {item.get('id')}: {item.get('fields', {}).get('System.Title', 'No title')}")
        else:
            print(f"Work item query also failed: {result2.stderr}")

except FileNotFoundError:
    print("❌ Azure CLI not installed")
    print("Install: brew install azure-cli")
except subprocess.TimeoutExpired:
    print("❌ Command timed out")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n")
