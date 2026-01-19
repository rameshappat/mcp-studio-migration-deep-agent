#!/usr/bin/env python3
"""Simple check using work item query - no MCP needed."""

import subprocess
import sys

project = "testingmcp"

print(f"\n=== Checking Test Case Work Items in {project} ===\n")

# Try to list all work items of type "Test Case"
result = subprocess.run([
    "az", "boards", "work-item", "show",
    "--id", "1163",
    "--org", "https://dev.azure.com/appatr"
], capture_output=True, text=True)

if result.returncode == 0:
    print("✅ Test case 1163 exists (from our manual fix)")
    print(result.stdout[:500])
else:
    print(f"❌ Test case 1163 not found: {result.stderr}")

print("\nℹ️  This was from our manual fix earlier.")
print("Now checking if the PIPELINE created any new test cases...")

# Check for recent test cases (created today)
result2 = subprocess.run([
    "az", "boards", "query",
    "--wiql", f"SELECT [System.Id], [System.Title], [System.CreatedDate] FROM WorkItems WHERE [System.WorkItemType] = 'Test Case' AND [System.CreatedDate] >= @Today - 1 ORDER BY [System.CreatedDate] DESC",
    "--org", "https://dev.azure.com/appatr",
    "--project", project
], capture_output=True, text=True, timeout=30)

if result2.returncode == 0:
    import json
    items = json.loads(result2.stdout)
    print(f"\n✅ Found {len(items)} test cases created in last 24 hours:")
    for item in items:
        print(f"  • ID {item.get('id')}: {item.get('fields', {}).get('System.Title', 'No title')}")
        print(f"    Created: {item.get('fields', {}).get('System.CreatedDate', 'Unknown')}")
else:
    print(f"\n❌ Query failed: {result2.stderr}")

print("\n")
