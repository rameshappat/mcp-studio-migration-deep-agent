import os
import requests
import json
import base64
import time

ORG = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
PROJECT = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
PAT = os.getenv("ADO_MCP_AUTH_TOKEN") or os.getenv("AZURE_DEVOPS_TOKEN")

if not PAT:
    raise RuntimeError("Azure DevOps PAT not found in environment variables.")

# Create a Test Case work item only
url = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/$Test%20Case?api-version=7.0"
auth_str = f":{PAT}"
auth_b64 = base64.b64encode(auth_str.encode()).decode()
headers = {
    "Content-Type": "application/json-patch+json",
    "Authorization": f"Basic {auth_b64}"
}

payload = [
    {"op": "add", "path": "/fields/System.Title", "value": "Direct API Test Case"},
    {"op": "add", "path": "/fields/System.AreaPath", "value": PROJECT},
    {"op": "add", "path": "/fields/System.IterationPath", "value": PROJECT},
    {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": "<steps id='0'/>"}
]

print(f"[DEBUG] Creating test case via REST API: {url}")
response = requests.post(url, headers=headers, data=json.dumps(payload))
print(f"[DEBUG] Status code: {response.status_code}")
try:
    print(f"[DEBUG] Response: {response.json()}")
except Exception:
    print(f"[DEBUG] Raw response: {response.text}")

if response.status_code == 200:
    tc_json = response.json()
    tc_id = tc_json.get("id")
    print(f"[SUCCESS] Test Case created successfully. ID: {tc_id}")
    print(f"[DEBUG] Test Case details: {json.dumps(tc_json, indent=2)}")
    print(f"[DEBUG] Test Case AreaPath: {tc_json.get('fields', {}).get('System.AreaPath')}")
    print(f"[DEBUG] Test Case IterationPath: {tc_json.get('fields', {}).get('System.IterationPath')}")
    print(f"[DEBUG] Test Case Project: {tc_json.get('fields', {}).get('System.TeamProject')}")

    # Only test case creation logic is retained. No test plan or suite association.
else:
    print("[ERROR] Failed to create Test Case.")
