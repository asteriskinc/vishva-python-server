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
from orcs.orchestration_agents import PlannerResponse, DependencyResponse, SubtaskSchema

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

async def send_status_update(websocket, subtask_id, status, message):
    """Send a status update through the WebSocket."""
    try:
        await websocket.send_json({
            "type": "SUBTASK_UPDATE",
            "payload": {
                "subtask_id": subtask_id,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        })
    except Exception as e:
        print(f"Error sending status update: {e}")

async def execute_task_workflow(task_id: str, executable_subtask_ids: set[str], websocket: WebSocket):
    """Execute the task workflow with real-time status updates."""
    try:
        task = orcs.tasks.get(task_id)
        if not task:
            await send_status_update(websocket, None, TaskStatus.FAILED, f"Task {task_id} not found")
            return

        # Initial status update
        await send_status_update(
            websocket, 
            None, 
            TaskStatus.IN_PROGRESS,
            f"Starting execution workflow for task: {task_id}"
        )

        # Filter executable subtasks
        filtered_task = task.model_copy()
        filtered_task.subtasks = [
            subtask for subtask in task.subtasks 
            if subtask.subtask_id in executable_subtask_ids
        ]

        # Update about subtask filtering
        await send_status_update(
            websocket,
            None,
            TaskStatus.IN_PROGRESS,
            f"Filtered {len(filtered_task.subtasks)} subtasks for execution"
        )

        # Calculate dependencies with status update
        await send_status_update(
            websocket,
            None,
            TaskStatus.IN_PROGRESS,
            "Calculating dependencies between subtasks..."
        )

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

        dependencies = await orcs.get_dependencies(filtered_task, planner_output)

        # Update dependencies in filtered task with status update
        subtask_dict = {subtask.subtask_id: subtask for subtask in filtered_task.subtasks}
        for dep in dependencies:
            if dep.subtask_id in subtask_dict:
                subtask_dict[dep.subtask_id].dependencies.append(dep)
                await send_status_update(
                    websocket,
                    dep.subtask_id,
                    TaskStatus.IN_PROGRESS,
                    f"Added dependency: {dep.task_id} -> {dep.subtask_id}"
                )

        # Begin execution with status updates
        orcs.tasks[task_id] = filtered_task
        
        async def status_callback(subtask_id, status, message):
            await send_status_update(websocket, subtask_id, status, message)
        
        result = await orcs.execute_task(filtered_task, status_callback=status_callback)

        # Final status update
        await send_status_update(
            websocket,
            None,
            result.status,
            f"Task execution completed: {result.message}"
        )

        return result

    except Exception as e:
        import traceback
        error_msg = f"Error in task execution: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        await send_status_update(websocket, None, TaskStatus.FAILED, error_msg)
        raise

@app.websocket("/api/task-execution/{task_id}")
async def task_execution_websocket(websocket: WebSocket, task_id: str):
    print(f"Received WebSocket connection for task: {task_id}")
    async with connections_lock:
        # Check if there's an existing connection and if it's still active
        if task_id in connections:
            try:
                # Try sending a ping to check if connection is alive
                await connections[task_id].send_json({"type": "PING"})
                # If we get here, the connection is still alive
                print(f"Active connection exists for task {task_id}, rejecting new connection")
                await websocket.close(1008, "Another connection already exists for this task")
                return
            except Exception:
                # If ping fails, the old connection is dead
                print(f"Removing stale connection for task {task_id}")
                del connections[task_id]
        
        # Accept the new connection
        print("accepting the new connection")
        await websocket.accept()
        connections[task_id] = websocket
        print(f"WebSocket connection established for task: {task_id}")
    
    try:
        print("starting the while loop")
        while True:
            data = await websocket.receive_json()
            print(f"Received message for task {task_id}:", data)
            print("received the message")
            if data["type"] == "START_EXECUTION":
                print("sending the ack")
                # Acknowledge receipt
                await websocket.send_json({
                    "type": "EXECUTION_STATUS",
                    "payload": {
                        "status": TaskStatus.IN_PROGRESS,
                        "message": "Starting task execution workflow"
                    }
                })
                print("sent the ack")
                
                try:
                    print("getting the subtasks")
                    # Get the list of subtasks to execute
                    executable_subtask_ids = {
                        subtask["subtask_id"] 
                        for subtask in data["payload"]["subtasks"]
                    }
                    
                    # Execute the task workflow with filtered subtasks
                    result = await execute_task_workflow(task_id, executable_subtask_ids, websocket)
                    
                    # Send completion status
                    if result:
                        print("sending the completion status")
                        await websocket.send_json({
                            "type": "EXECUTION_STATUS",
                            "payload": {
                                "status": result.status,
                                "message": result.message
                            }
                        })
                except Exception as e:
                    print(f"Error executing task {task_id}:", str(e))
                    print("sending the failure status")
                    await websocket.send_json({
                        "type": "EXECUTION_STATUS",
                        "payload": {
                            "status": TaskStatus.FAILED,
                            "message": f"Task execution failed: {str(e)}"
                        }
                    })
                
    except WebSocketDisconnect:
        print("websocket disconnect")
        async with connections_lock:
            if task_id in connections and connections[task_id] == websocket:
                del connections[task_id]
                print(f"WebSocket connection closed for task: {task_id}")
    except Exception as e:
        print(f"Error in WebSocket connection for task {task_id}:", str(e))
        print("deleting the task id")
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