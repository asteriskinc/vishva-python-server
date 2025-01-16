# server.py
from datetime import datetime
from typing import Dict
import asyncio, json, os, uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orcs.core import ORCS
from orcs.execution_agents import EXECUTION_AGENTS
from orcs.orcs_types import Task, TaskStatus

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Vishva API")

# Initialize ORCS with execution agents
orcs = ORCS(api_key=os.getenv('OPENAI_API_KEY'))
orcs.agents = EXECUTION_AGENTS

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.get("/")
async def read_root():
    return {"status": "healthy", "message": "Vishva API is running"}

@app.post("/api/process-query")
async def process_query(request: QueryRequest):
    try:
        print(f"\nReceived query: {request.query}")
        
        # Use ORCS to create task from query
        task = await orcs.convert_query_to_task(request.query)
        
        # Store the task in ORCS's internal state for later execution
        orcs.tasks[task.task_id] = task
        
        # Convert to dict and print
        task_dict = task.model_dump(mode='json')
        
        return task_dict
        
    except Exception as e:
        import traceback
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print("Error processing query:", error_detail)
        raise HTTPException(status_code=500, detail=str(error_detail))
    
# Store active websocket connections with a lock for thread safety
connections: Dict[str, WebSocket] = {}
connections_lock = asyncio.Lock()

async def execute_task_workflow(task_id: str, executable_subtask_ids: set[str]):
    """
    Execute the task workflow using ORCS:
    1. Get task from ORCS's state
    2. Calculate dependencies
    3. Execute the task with only the executable subtasks
    """
    try:
        # Get the task from ORCS's state
        task = orcs.tasks.get(task_id)
        if not task:
            print(f"Task {task_id} not found in ORCS state")
            return

        print(f"\nStarting execution workflow for task: {task_id}")
        print("="*50)
        
        # Step 1: Create a filtered task with only executable subtasks
        filtered_task = task.model_copy()
        filtered_task.subtasks = [
            subtask for subtask in task.subtasks 
            if subtask.subtask_id in executable_subtask_ids
        ]
        
        print("\nExecutable Subtasks:")
        for i, subtask in enumerate(filtered_task.subtasks, start=1):
            print(f"{i}. Subtask ID: {subtask.subtask_id}, Title: {subtask.title}")
        
        # Create PlannerResponse for dependency calculation
        from orcs.orchestration_agents import PlannerResponse, SubtaskSchema
        planner_output = PlannerResponse(
            domain=filtered_task.domain or "general",
            needsClarification=filtered_task.needsClarification,
            clarificationPrompt=filtered_task.clarificationPrompt or "",
            subtasks=[
                SubtaskSchema(
                    title=subtask.title,
                    agent=subtask.agent.name,
                    detail=subtask.detail,
                    category=subtask.category
                )
                for subtask in filtered_task.subtasks
            ]
        )
        
        # Step 2: Calculate Dependencies for filtered subtasks
        print("\nStep 2: Calculating Dependencies...")
        start_time = datetime.now()
        dependencies = await orcs.get_dependencies(filtered_task, planner_output)
        
        # Update dependencies in filtered task
        subtask_dict = {subtask.subtask_id: subtask for subtask in filtered_task.subtasks}
        for dep in dependencies:
            if dep.subtask_id in subtask_dict:
                subtask_dict[dep.subtask_id].dependencies.append(dep)
        
        dependency_calc_time = (datetime.now() - start_time).total_seconds()
        print(f"Dependencies calculated in {dependency_calc_time:.2f} seconds")
        
        # Step 3: Execute filtered task
        print("\nStep 3: Beginning Task Execution...")
        start_time = datetime.now()
        
        # Update the task in ORCS state to only include executable subtasks
        orcs.tasks[task_id] = filtered_task
        result = await orcs.execute_task(filtered_task)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        print(f"\nTask execution completed in {execution_time:.2f} seconds")
        print(f"Final Status: {result.status}")
        print(f"Execution Message: {result.message}")
        print("="*50)
        
        return result
        
    except Exception as e:
        import traceback
        print(f"Error in task execution workflow:")
        print(traceback.format_exc())
        raise

@app.websocket("/api/task-execution/{task_id}")
async def task_execution_websocket(websocket: WebSocket, task_id: str):
    async with connections_lock:
        # If there's an existing connection for this task, close it
        if task_id in connections:
            try:
                await connections[task_id].close()
            except:
                pass
            await asyncio.sleep(0.1)  # Give a small delay for cleanup
        
        # Accept the new connection
        await websocket.accept()
        connections[task_id] = websocket
        print(f"WebSocket connection established for task: {task_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received message for task {task_id}:", data)
            
            if data["type"] == "START_EXECUTION":
                # Acknowledge receipt
                await websocket.send_json({
                    "type": "EXECUTION_STATUS",
                    "payload": {
                        "status": TaskStatus.IN_PROGRESS,
                        "message": "Starting task execution workflow"
                    }
                })
                
                try:
                    # Get the list of subtasks to execute
                    executable_subtask_ids = {
                        subtask["subtask_id"] 
                        for subtask in data["payload"]["subtasks"]
                    }
                    
                    # Execute the task workflow with filtered subtasks
                    result = await execute_task_workflow(task_id, executable_subtask_ids)
                    
                    # Send completion status
                    if result:
                        await websocket.send_json({
                            "type": "EXECUTION_STATUS",
                            "payload": {
                                "status": result.status,
                                "message": result.message
                            }
                        })
                except Exception as e:
                    print(f"Error executing task {task_id}:", str(e))
                    await websocket.send_json({
                        "type": "EXECUTION_STATUS",
                        "payload": {
                            "status": TaskStatus.FAILED,
                            "message": f"Task execution failed: {str(e)}"
                        }
                    })
                
    except WebSocketDisconnect:
        async with connections_lock:
            if task_id in connections and connections[task_id] == websocket:
                del connections[task_id]
                print(f"WebSocket connection closed for task: {task_id}")
    except Exception as e:
        print(f"Error in WebSocket connection for task {task_id}:", str(e))
        async with connections_lock:
            if task_id in connections and connections[task_id] == websocket:
                del connections[task_id]

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )