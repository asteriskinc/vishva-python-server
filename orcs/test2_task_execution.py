# test2_task_execution.py
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from core import ORCS
from execution_agents import EXECUTION_AGENTS
from orcs_types import TaskStatus

def print_task_creation_details(task):
    """Helper function to print initial task details"""
    print(f"\nTask Creation Details:")
    print(f"Task ID: {task.task_id}")
    print(f"Initial Status: {task.status}")
    print(f"Creation Time: {task.start_time}")
    print("\nPlanned Subtasks:")
    
    for subtask in task.subtasks:
        print(f"\n- {subtask.title}")
        print(f"  Agent: {subtask.agent.name}")
        print(f"  Detail: {subtask.detail}")
        if subtask.dependencies:
            print("  Dependencies:")
            for dep in subtask.dependencies:
                dependent_task = next(
                    (t for t in task.subtasks if t.subtask_id == dep.task_id),
                    None
                )
                dependent_title = dependent_task.title if dependent_task else "Unknown Task"
                print(f"    - Depends on: {dependent_title}")

def print_execution_results(result, task, completed_results):
    """Helper function to print execution results"""
    print("\nExecution Results:")
    print(f"Final Status: {result.status}")
    print(f"Execution Message: {result.message}")
    print(f"Completion Time: {result.timestamp}")
    
    if result.status == TaskStatus.COMPLETED and "completed_subtasks" in result.data:
        print("\nSubtask Results:")
        for subtask in task.subtasks:
            subtask_result = completed_results.get(subtask.subtask_id)
            if subtask_result:
                print(f"\n- {subtask.title}:")
                print(f"  Status: {subtask_result.status}")
                print(f"  Execution Time: {subtask_result.timestamp}")
                print(f"  Result Data:")
                
                # Print agent-specific results
                if subtask.agent.name == "Location Agent":
                    for location in subtask_result.data.get("locations", []):
                        print(f"    - {location['address']}")
                        if "additional_info" in location:
                            print(f"      Additional Info: {location['additional_info']}")
                
                elif subtask.agent.name == "Search Agent":
                    results = subtask_result.data.get("results", [])
                    print(f"    Found {len(results)} results")
                    for result in results[:3]:  # Show top 3
                        print(f"    - {result['title']}")
                        print(f"      Relevance: {result['relevance_score']}")
                
                elif subtask.agent.name == "Scheduling Agent":
                    schedule = subtask_result.data.get("schedule", {})
                    print(f"    Time: {schedule.get('event_time')}")
                    print(f"    Duration: {schedule.get('duration')} minutes")
                
                elif subtask.agent.name == "Navigation Agent":
                    print(f"    Route from: {subtask_result.data.get('start_location')}")
                    print(f"    Route to: {subtask_result.data.get('end_location')}")
                    print(f"    Total distance: {subtask_result.data.get('total_distance')}")
                
                elif subtask.agent.name == "Concierge Agent":
                    for rec in subtask_result.data.get("recommendations", [])[:3]:
                        print(f"    - {rec['title']}")
                        print(f"      Rating: {rec['rating']}")
                        if rec.get("price_range"):
                            print(f"      Price: {rec['price_range']}")

async def test_task_execution():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")

    try:
        # Initialize ORCS with execution agents
        orcs = ORCS(api_key=api_key)
        orcs.agents = EXECUTION_AGENTS

        # Test queries representing different complexity levels
        test_queries = [
            # Simple query with two dependent tasks
            "Find an Italian restaurant near Central Park for tonight",
            
            # Complex query with multiple dependencies
            "Plan a movie night with dinner for 4 people this Saturday",
            
            # Very complex query with many interdependent tasks
            "Organize a birthday dinner party for 8 people at a nice restaurant next week"
        ]

        for query in test_queries:
            print(f"\n{'='*80}")
            print(f"Testing Query: {query}")
            print(f"{'='*80}")

            try:
                # Step 1: Create the task
                print("\nStep 1: Creating Task...")
                start_time = datetime.now()
                task = await orcs.convert_query_to_task(query)
                creation_time = (datetime.now() - start_time).total_seconds()
                
                print(f"Task created in {creation_time:.2f} seconds")
                print_task_creation_details(task)

                # Viewing the dependency structure
                orcs.print_dependency_structure(task.task_id)

                # Step 2: Execute the task
                print("\nStep 2: Executing Task...")
                start_time = datetime.now()
                result = await orcs.execute_task(task)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                print(f"Task executed in {execution_time:.2f} seconds")
                print_execution_results(result, task, orcs.completed_results)

            except Exception as e:
                print(f"\nError processing query '{query}':")
                print(f"Error: {str(e)}")

    except Exception as e:
        import traceback
        print(f"Error during test execution: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_task_execution())