#!/usr/bin/env python
"""Check ADO status - work items and test plans."""

import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

async def check_status():
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    await client.connect()
    
    print("=" * 60)
    print("ADO PROJECT STATUS")
    print("=" * 60)
    
    # Check test plans
    print("\n📋 Test Plans:")
    try:
        result = await client.call_tool('testplan_list_test_plans', {})
        
        # The result is a list of plan dictionaries
        if isinstance(result, list):
            if result:
                print(f"  ✅ Found {len(result)} test plan(s)")
                for plan in result:
                    plan_id = plan.get('id')
                    plan_name = plan.get('name', 'Unnamed')
                    root_suite = plan.get('rootSuite', {})
                    suite_id = root_suite.get('id', 'N/A')
                    suite_name = root_suite.get('name', 'N/A')
                    state = plan.get('state', 'Unknown')
                    print(f"\n    Plan ID: {plan_id}")
                    print(f"    Name: {plan_name}")
                    print(f"    Root Suite ID: {suite_id}")
                    print(f"    Root Suite Name: {suite_name}")
                    print(f"    State: {state}")
            else:
                print(f"  ℹ️  No test plans found")
    except Exception as e:
        print(f"  ❌ Error listing test plans: {e}")
    
    await client.close()
    
    print("\n" + "=" * 60)
    print("STATUS CHECK COMPLETE")
    print("=" * 60)

asyncio.run(check_status())
