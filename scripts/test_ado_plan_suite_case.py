"""
Standalone test for Azure DevOps Test Plan, Suite, and Test Case creation and verification.
"""



import os
import asyncio
import traceback
from src.mcp_client.ado_client import AzureDevOpsMCPClient


import asyncio

ORG = os.getenv("ADO_ORG", "appatr")
PROJECT = os.getenv("ADO_PROJECT", "testingmcp")



async def run_with_timeout(coro, timeout, step_name):
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] {step_name} timed out after {timeout} seconds.")
        return None
    except Exception as e:
        print(f"[ERROR] {step_name} failed: {e}")
        traceback.print_exc()
        return None

async def main():
    print(f"[DEBUG] Using ORG={ORG}, PROJECT={PROJECT}")

    try:
        client = AzureDevOpsMCPClient(organization=ORG, project=PROJECT)
        await run_with_timeout(client.connect(), 30, "Connect MCP Client")
        print("[DEBUG] Connected to Azure DevOps MCP Client.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Azure DevOps MCP Client: {e}")
        traceback.print_exc()
        return

    # 1. Create Test Plan
    print("[DEBUG] Creating Test Plan...")
    test_plan = await run_with_timeout(
        client.create_test_plan(name="Standalone Test Plan", iteration="StandaloneIteration"),
        30,
        "Create Test Plan"
    )
    print(f"[DEBUG] Test Plan response: {test_plan}")
    if not test_plan or "id" not in test_plan:
        print("[ERROR] Test Plan creation failed or timed out.")
        return

    # 2. Create Test Suite
    print("[DEBUG] Creating Test Suite...")
    suite = await run_with_timeout(
        client.create_test_suite(plan_id=test_plan["id"], name="Standalone Test Suite"),
        30,
        "Create Test Suite"
    )
    print(f"[DEBUG] Test Suite response: {suite}")
    if not suite or "id" not in suite:
        print("[ERROR] Test Suite creation failed or timed out.")
        return

    # 3. Add Test Cases
    case_ids = []
    for i in range(2):
        print(f"[DEBUG] Creating Test Case {i+1}...")
        case = await run_with_timeout(
            client.create_test_case(
                title=f"Standalone Test Case {i+1}",
                steps="1. Step one|Expected result one",
                priority=2,
                area_path=None,
                iteration_path=None,
                tests_work_item_id=None,
            ),
            30,
            f"Create Test Case {i+1}"
        )
        print(f"[DEBUG] Test Case {i+1} response: {case}")
        if case and "id" in case:
            case_ids.append(case["id"])

    if not case_ids:
        print("[ERROR] No test cases were created. Exiting.")
        return

    # 4. Add test cases to suite
    print("[DEBUG] Adding test cases to suite...")
    added = await run_with_timeout(
        client.add_test_cases_to_suite(
            plan_id=test_plan["id"],
            suite_id=suite["id"],
            test_case_ids=case_ids,
            project=PROJECT,
        ),
        30,
        "Add Test Cases to Suite"
    )
    print(f"[DEBUG] Add-to-suite response: {added}")

    # 5. Verify by listing test cases in the suite
    print("[DEBUG] Verifying test cases in suite...")
    cases = await run_with_timeout(
        client._call_first_available_tool(
            ["testplan_list_test_cases", "mcp_ado_testplan_list_test_cases"],
            {"project": PROJECT, "planid": test_plan["id"], "suiteid": suite["id"]},
        ),
        30,
        "List Test Cases in Suite"
    )
    listed = cases.get("value") if isinstance(cases, dict) else None
    print(f"[INFO] Test Cases in Suite:")
    if isinstance(listed, list):
        for row in listed:
            tc = (row or {}).get("testCase") if isinstance(row, dict) else None
            if isinstance(tc, dict) and "id" in tc:
                print(f"- {tc['id']}")
    else:
        print(f"[DEBUG] Suite verification result: {cases}")

    print("[SUCCESS] Standalone ADO test plan/suite/case creation and verification completed.")

if __name__ == "__main__":
    asyncio.run(main())
