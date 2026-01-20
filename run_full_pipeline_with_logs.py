"""
Run the full autonomous pipeline with detailed logging
"""
import asyncio
import logging
import sys
from datetime import datetime

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

async def main():
    print("="*100)
    print("AUTONOMOUS SDLC PIPELINE - FULL RUN WITH DETAILED LOGS")
    print("="*100)
    print(f"Start Time: {datetime.now()}")
    print()
    
    # Import the graph builder
    from src.studio_graph_autonomous import build_graph
    
    # Build the graph
    logger.info("Building graph...")
    compiled_graph = build_graph()
    logger.info("✅ Graph compiled successfully")
    print()
    
    # Create initial state with a simple query
    user_query = "Build a wealth management client onboarding system with React frontend, Spring Boot backend, OAuth 2.0 authentication, and Azure SQL database"
    
    initial_state = {
        "user_query": user_query,
        "project_name": "wealth-management-onboarding",  # Provide upfront to skip interrupt
    }
    
    print("="*100)
    print("INITIAL INPUT")
    print("="*100)
    print(f"User Query: {user_query}")
    print()
    
    # Run the graph
    logger.info("Starting graph execution...")
    print("="*100)
    print("EXECUTION LOG")
    print("="*100)
    
    try:
        config = {
            "recursion_limit": 50,
        }
        
        # Use invoke instead of stream to avoid interrupts
        print("Running full pipeline (non-interactive mode)...")
        print()
        
        final_state = await compiled_graph.ainvoke(initial_state, config=config)
        
        print()
        print("="*100)
        print("FINAL STATE")
        print("="*100)
        print(f"✅ Pipeline Complete: {final_state.get('pipeline_complete', False)}")
        print(f"📋 Has Requirements: {final_state.get('requirements') is not None}")
        print(f"📋 Work Items: {final_state.get('work_items', {}).get('created_ids', []) if final_state.get('work_items') else 'None'}")
        print(f"🧪 Test Plan Complete: {final_state.get('test_plan_complete', False)}")
        print(f"🧪 Test Cases: {final_state.get('test_cases', 'None')}")
        print(f"🏗️  Architecture: {'✅' if final_state.get('architecture') else '❌'}")
        print(f"💻 Code: {'✅' if final_state.get('code_artifacts') else '❌'}")
        print(f"❌ Errors: {final_state.get('errors', [])}")
        
        # Check messages for debugging
        messages = final_state.get('messages', [])
        if messages:
            print()
            print("="*100)
            print("AGENT MESSAGES")
            print("="*100)
            for msg in messages[-10:]:  # Last 10 messages
                if isinstance(msg, dict):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    print(f"{role}: {content[:200]}")
        
        # Check orchestrator decisions
        decision_history = final_state.get('decision_history', [])
        if decision_history:
            print()
            print("="*100)
            print("ORCHESTRATOR DECISIONS")
            print("="*100)
            for i, decision in enumerate(decision_history, 1):
                print(f"{i}. {decision.get('agent')} -> {decision.get('decision')}")
                
        # Most importantly - check if test_plan agent was involved
        print()
        print("="*100)
        print("TEST PLAN AGENT STATUS")
        print("="*100)
        
        # Look for test plan messages
        test_plan_messages = [m for m in messages if isinstance(m, dict) and m.get('role') == 'qa_manager']
        if test_plan_messages:
            print("✅ Test Plan Agent DID execute!")
            for msg in test_plan_messages:
                print(f"   {msg.get('content', '')[:300]}")
        else:
            print("❌ Test Plan Agent DID NOT execute!")
            print("   No messages from qa_manager role found.")
            
        # Check the test_plan_complete flag progression
        print()
        print(f"Final test_plan_complete flag: {final_state.get('test_plan_complete', 'Not Set')}")
        
    except Exception as e:
        print()
        print("="*100)
        print("EXCEPTION OCCURRED")
        print("="*100)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("="*100)
    print(f"End Time: {datetime.now()}")
    print("="*100)

if __name__ == "__main__":
    asyncio.run(main())
