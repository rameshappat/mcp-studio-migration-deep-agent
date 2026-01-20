"""Test generation of a single test case with improved prompt."""
import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


async def test_single_case():
    """Generate one test case to verify quality."""
    from src.studio_graph_autonomous import get_ado_client
    
    ado_client = get_ado_client()
    llm = ChatOpenAI(model="gpt-4", temperature=0.3)
    
    # Get work item 1243 (React Client Dashboard)
    print("Fetching work item 1243...")
    wi_details = await ado_client.get_work_item(work_item_id=1243)
    fields = wi_details.get("fields", {})
    
    wi_data = {
        "id": 1243,
        "title": fields.get("System.Title", ""),
        "description": fields.get("System.Description", ""),
        "work_item_type": fields.get("System.WorkItemType", ""),
        "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
    }
    
    print(f"\nWork Item Details:")
    print(f"  ID: {wi_data['id']}")
    print(f"  Type: {wi_data['work_item_type']}")
    print(f"  Title: {wi_data['title']}")
    print(f"  Description: {wi_data['description'][:200] if wi_data['description'] else 'None'}")
    
    # Generate test case using new prompt
    prompt = f"""You are a QA engineer creating a comprehensive test case for this work item:

WORK ITEM DETAILS:
Type: {wi_data['work_item_type']}
Title: {wi_data['title']}
Description: {wi_data['description'] or 'Not provided'}
Acceptance Criteria: {wi_data['acceptance_criteria'] or 'Not provided'}

YOUR TASK:
Create a detailed, professional test case that validates this requirement.

TEST TITLE:
- Must be clear and specific (max 128 chars)
- Should indicate what is being tested
- Include the main feature/functionality name

TEST STEPS:
- Create 4-6 comprehensive test steps
- Each step should be actionable and specific
- Include setup, execution, and validation steps
- Cover positive scenarios and edge cases where applicable
- Format: "Step description|Expected result"
- Use '|' as delimiter between step and expected result
- Be specific about what to verify in expected results

RESPONSE FORMAT (follow exactly):
TEST_TITLE: [Clear, specific title reflecting the requirement]
TEST_STEPS:
1. [Specific setup/precondition step]|[What should be ready]
2. [First action to test the feature]|[Expected outcome with specific details]
3. [Second action or validation]|[Expected result with measurable criteria]
4. [Edge case or error scenario if applicable]|[Expected behavior]
5. [Verify integration points or side effects]|[Expected state]
6. [Cleanup or final validation]|[Expected final state]

Generate the test case now:"""

    print("\n" + "="*80)
    print("GENERATING TEST CASE WITH LLM...")
    print("="*80)
    
    response = llm.invoke(prompt)
    llm_content = response.content
    
    print("\nLLM Response:")
    print("="*80)
    print(llm_content)
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_single_case())
