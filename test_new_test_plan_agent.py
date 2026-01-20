"""Test the new LLM-based test plan agent."""
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_new_agent():
    """Test the new test plan agent approach."""
    from src.studio_graph_autonomous import test_plan_agent_node, DeepPipelineState
    
    # Create a minimal state
    state: DeepPipelineState = {
        "messages": [],
        "user_query": "Test query",
        "consecutive_failures": {},
    }
    
    logger.info("="*80)
    logger.info("Testing NEW test plan agent (REST API + LLM)")
    logger.info("="*80)
    
    try:
        result = await test_plan_agent_node(state)
        
        logger.info("\n" + "="*80)
        logger.info("RESULT:")
        logger.info("="*80)
        logger.info(f"Test cases created: {len(result.get('test_cases', []))}")
        logger.info(f"Test plan complete: {result.get('test_plan_complete')}")
        
        if result.get('test_cases'):
            logger.info("\nTest cases:")
            for tc in result['test_cases']:
                logger.info(f"  - ID {tc['test_case_id']}: {tc['title']}")
        
        if result.get('failed_tool_calls'):
            logger.warning(f"\nFailed operations: {len(result['failed_tool_calls'])}")
            for failure in result['failed_tool_calls']:
                logger.warning(f"  - {failure['tool']}: {failure['error'][:100]}")
        
        return result
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(test_new_agent())
