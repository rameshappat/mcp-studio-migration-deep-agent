#!/usr/bin/env python3
"""Test guardrail-enhanced LLM output parsing."""

import re

def test_work_item_id_extraction():
    """Test work item ID extraction with guardrail patterns."""
    
    test_outputs = [
        # Guardrail format 1: Full URLs
        """Created work item: https://dev.azure.com/appatr/testingmcp/_workitems/edit/1406
        Created work item: https://dev.azure.com/appatr/testingmcp/_workitems/edit/1407
        Created work item: https://dev.azure.com/appatr/testingmcp/_workitems/edit/1408""",
        
        # Guardrail format 2: Summary section
        """
        === WORK ITEMS CREATED ===
        - https://dev.azure.com/appatr/testingmcp/_workitems/edit/1410
        - https://dev.azure.com/appatr/testingmcp/_workitems/edit/1411
        === TOTAL: 2 WORK ITEMS ===
        """,
        
        # Old format (should still work)
        """Created work items at /edit/1420, /edit/1421, /edit/1422""",
        
        # Mixed format
        """I've created the following work items:
        Work item ID 1430 - Epic: System Architecture
        Work item ID: 1431 - Issue: Frontend Development
        Work item ID: 1432 - Issue: Backend API""",
        
        # Worst case: minimal info
        """All work items created successfully. IDs: 1440, 1441, 1442""",
    ]
    
    for i, output in enumerate(test_outputs, 1):
        print(f"\n{'='*60}")
        print(f"TEST CASE {i}")
        print(f"{'='*60}")
        print(f"Output snippet:\n{output[:100]}...")
        
        created_ids = []
        
        # Pattern 1: Full URL format (from guardrails)
        url_pattern = r'https://dev\.azure\.com/appatr/testingmcp/_workitems/edit/(\d+)'
        url_matches = re.findall(url_pattern, output)
        
        # Pattern 2: Short URL format /edit/1234
        short_pattern = r'/edit/(\d+)'
        short_matches = re.findall(short_pattern, output)
        
        # Pattern 3: "work item: [URL]" format
        wi_pattern = r'work item.*?/edit/(\d+)'
        wi_matches = re.findall(wi_pattern, output, re.IGNORECASE)
        
        # Pattern 4: Direct ID mentions "ID 1234" or "ID: 1234"
        id_pattern = r'\bID:?\s*(\d{3,})\b'
        id_matches = re.findall(id_pattern, output, re.IGNORECASE)
        
        # Pattern 5: Comma-separated IDs in lists
        list_pattern = r'IDs?:\s*([\d,\s]+)'
        list_matches = re.findall(list_pattern, output, re.IGNORECASE)
        if list_matches:
            # Parse comma-separated numbers
            for match in list_matches:
                nums = re.findall(r'\d{3,}', match)
                id_matches.extend(nums)
        
        # Combine all matches
        all_matches = url_matches + short_matches + wi_matches + id_matches
        created_ids = list(set([int(id_str) for id_str in all_matches]))  # Remove duplicates
        created_ids.sort()  # Sort for consistency
        
        print(f"\n✅ Extracted IDs: {created_ids}")
        print(f"   Total: {len(created_ids)} work items")
        print(f"   URL matches: {len(url_matches)}")
        print(f"   Short matches: {len(short_matches)}")
        print(f"   WI pattern: {len(wi_matches)}")
        print(f"   ID pattern: {len(id_matches)}")


def test_completion_signals():
    """Test completion signal detection."""
    
    test_outputs = [
        ("Requirements output", "# Requirements\n\nAll done!\n\nREQUIREMENTS_COMPLETE"),
        ("Test plan output", "Created 5 test cases\n\nTEST_PLAN_COMPLETE"),
        ("Architecture output", "System design complete\n\nARCHITECTURE_COMPLETE"),
        ("Work items output", "=== WORK ITEMS CREATED ===\nAll items\n=== TOTAL: 10 WORK ITEMS ==="),
        ("No signal", "This work is complete but no signal"),
    ]
    
    completion_signals = [
        "REQUIREMENTS_COMPLETE",
        "TEST_PLAN_COMPLETE", 
        "ARCHITECTURE_COMPLETE",
        "=== TOTAL:",
        "=== WORK ITEMS CREATED ===",
    ]
    
    print(f"\n{'='*60}")
    print("COMPLETION SIGNAL DETECTION")
    print(f"{'='*60}")
    
    for name, output in test_outputs:
        print(f"\n{name}:")
        output_upper = output.upper()
        detected = None
        for signal in completion_signals:
            if signal.upper() in output_upper:
                detected = signal
                break
        
        if detected:
            print(f"  ✅ Detected: {detected}")
        else:
            print(f"  ❌ No completion signal detected")


if __name__ == "__main__":
    print("TESTING GUARDRAIL-ENHANCED LLM OUTPUT PARSING")
    print("=" * 60)
    
    test_work_item_id_extraction()
    test_completion_signals()
    
    print(f"\n{'='*60}")
    print("✅ All tests complete!")
    print("=" * 60)
