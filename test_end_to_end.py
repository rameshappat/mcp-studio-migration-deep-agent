"""Test end-to-end: Create work items then generate test cases."""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_end_to_end():
    """Test the full flow: create work items, then generate test cases."""
    from src.studio_graph_autonomous import test_plan_agent_node, get_ado_client, DeepPipelineState
    
    ado_client = get_ado_client()
    project = os.getenv("AZURE_DEVOPS_PROJECT", "testingmcp")
    
    # STEP 1: Create sample work items
    logger.info("="*80)
    logger.info("STEP 1: Creating sample work items")
    logger.info("="*80)
    
    work_items_to_create = [
        {
            "title": "User Authentication API",
            "type": "Issue",
            "description": "Implement OAuth 2.0 authentication for REST API",
        },
        {
            "title": "Dashboard UI Component",
            "type": "Issue",
            "description": "Create React dashboard with real-time data visualization",
        },
        {
            "title": "Database Schema Migration",
            "type": "Issue",
            "description": "Migrate from SQL Server to Azure SQL with encryption",
        },
    ]
    
    created_ids = []
    for wi in work_items_to_create:
        try:
            result = await ado_client.create_work_item(
                project=project,
                work_item_type=wi['type'],
                title=wi['title'],
                description=wi['description'],
            )
            
            if isinstance(result, dict) and "error" not in result:
                wi_id = result.get("id")
                created_ids.append(wi_id)
                logger.info(f"✅ Created work item {wi_id}: {wi['title']}")
            else:
                logger.error(f"❌ Failed to create: {wi['title']}")
        except Exception as e:
            logger.error(f"❌ Exception creating {wi['title']}: {e}")
    
    logger.info(f"\nCreated {len(created_ids)} work items: {created_ids}")
    
    # Give ADO a moment to index the work items
    logger.info("\n⏱️  Waiting 2 seconds for ADO indexing...")
    await asyncio.sleep(2)
    
    # STEP 2: Run test plan agent
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Running test plan agent")
    logger.info("="*80)
    
    state: DeepPipelineState = {
        "messages": [],
        "user_query": "Generate test cases",
        "consecutive_failures": {},
    }
    
    result = await test_plan_agent_node(state)
    
    # STEP 3: Check results
    logger.info("\n" + "="*80)
    logger.info("STEP 3: Results")
    logger.info("="*80)
    logger.info(f"Work items created: {len(created_ids)}")
    logger.info(f"Test cases created: {len(result.get('test_cases', []))}")
    
    if result.get('test_cases'):
        logger.info("\n✅ Test cases generated:")
        for tc in result['test_cases']:
            logger.info(f"  - ID {tc['test_case_id']}: {tc['title']}")
            logger.info(f"    Linked to work item: {tc['work_item_id']}")
    else:
        logger.error("\n❌ No test cases were created!")
    
    if result.get('failed_tool_calls'):
        logger.warning(f"\n⚠️  Failed operations: {len(result['failed_tool_calls'])}")
        for failure in result['failed_tool_calls'][:3]:
            logger.warning(f"  - {failure['tool']}: {failure['error'][:100]}")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_end_to_end())
