# test1_query_to_task_creation.py
import asyncio
import os
from dotenv import load_dotenv
from core import ORCS
from execution_agents import EXECUTION_AGENTS

async def test_orcs():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")

    try:
        # Initialize ORCS
        orcs = ORCS(api_key=api_key)

        # Initialize available agents
        orcs.agents = EXECUTION_AGENTS

        # Test queries
        test_queries = [
            "Help me find and book tickets for a movie this weekend and suggest some dinner options nearby",
            "I need to plan a birthday party at a restaurant next week for 8 people"
        ]

        for query in test_queries:
            print(f"\n{'='*80}")
            print(f"Processing query: {query}")
            print(f"{'='*80}\n")

            # Create task from query
            task = await orcs.convert_query_to_task(query)
            
            # Print task details
            print(f"Task ID: {task.task_id}")
            print(f"Status: {task.status}")
            print(f"Start Time: {task.start_time}")
            print("\nSubtasks:")
            
            for subtask in task.subtasks:
                print(f"\n- Subtask ID: {subtask.subtask_id}")
                print(f"  Title: {subtask.title}")
                print(f"  Agent: {subtask.agent.name}")
                print(f"  Detail: {subtask.detail}")
                print(f"  Status: {subtask.status}")
                
                if subtask.dependencies:
                    print("  Dependencies:")
                    for dep in subtask.dependencies:
                        # Get the title of the dependency for better readability
                        dependent_task = next(
                            (t for t in task.subtasks if t.subtask_id == dep.task_id),
                            None
                        )
                        dependent_title = dependent_task.title if dependent_task else "Unknown Task"
                        print(f"    - Depends on: {dependent_title} ({dep.task_id})")
                else:
                    print("  Dependencies: None")

    except Exception as e:
        import traceback
        print(f"Error during test: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_orcs())