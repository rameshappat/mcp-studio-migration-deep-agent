#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'src')
import asyncio
from mcp_client.ado_client import AzureDevOpsMCPClient

async def check():
    org = os.getenv("AZURE_DEVOPS_ORG", "appatr")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    client = AzureDevOpsMCPClient(organization=org, project=project)
    await client.connect()
    
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    test_plan_id = int(os.getenv("SDLC_TESTPLAN_ID", "369"))
    test_suite_id = int(os.getenv("SDLC_TESTSUITE_ID", "370"))
    
    print(f"\n=== ADO State Check ===")
    print(f"Project: {project}")
    print(f"Test Plan: {test_plan_id}")
    print(f"Test Suite: {test_suite_id}\n")
    
    try:
        cases = await client.call_tool('testplan_list_test_cases', {
            'project': project,
            'planid': test_plan_id,
            'suiteid': test_suite_id
        }, timeout=15)  # 15 second timeout
        
        print(f"Test Cases in Suite {test_suite_id}: {len(cases) if cases else 0}")
        
        if cases:
            print("\nTest Cases Found:")
            for case in cases:
                wi = case.get('workItem', {})
                print(f"  • ID {wi.get('id')}: {wi.get('name', 'No name')}")
        else:
            print("❌ NO TEST CASES FOUND IN SUITE")
            
    except Exception as e:
        print(f"Error: {e}")
    
    await client.close()

asyncio.run(check())
