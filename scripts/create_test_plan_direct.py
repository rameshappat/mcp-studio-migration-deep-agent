
import os
import requests
import json
import base64

ORG = os.getenv("AZURE_DEVOPS_ORGANIZATION", "appatr")
PROJECT = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
PAT = os.getenv("ADO_MCP_AUTH_TOKEN") or os.getenv("AZURE_DEVOPS_TOKEN")

if not PAT:
    raise RuntimeError("Azure DevOps PAT not found in environment variables.")

url = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/testplan/plans?api-version=7.0"
auth_str = f":{PAT}"
auth_b64 = base64.b64encode(auth_str.encode()).decode()
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {auth_b64}"
}

payload = {
    "name": "Direct API Test Plan",
    "areaPath": PROJECT,
    "iteration": PROJECT
}

print(f"[DEBUG] Creating test plan via REST API: {url}")
response = requests.post(url, headers=headers, data=json.dumps(payload))

print(f"[DEBUG] Status code: {response.status_code}")
try:
    print(f"[DEBUG] Response: {response.json()}")
except Exception:
    print(f"[DEBUG] Raw response: {response.text}")

if response.status_code == 200:
    print("[SUCCESS] Test Plan created successfully.")
else:
    print("[ERROR] Failed to create Test Plan.")
