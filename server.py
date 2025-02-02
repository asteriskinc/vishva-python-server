# server.py
from datetime import datetime
from typing import Dict, Optional
import asyncio, json, os, uvicorn, traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orcs.core import ORCS
from orcs.execution_agents import EXECUTION_AGENTS
from orcs.orcs_types import Task, TaskStatus, TaskResult
from orcs.orchestration_agents import PlannerResponse, DependencyResponse, SubtaskSchema
from websocket_manager import WebSocketManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Vishva API")

# Initialize ORCS with execution agents
orcs = ORCS(api_key=os.getenv('OPENAI_API_KEY'))
orcs.agents = EXECUTION_AGENTS

# Initialize WebSocketManager
websocket_manager = WebSocketManager()

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
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print("Error processing query:", error_detail)
        raise HTTPException(status_code=500, detail=str(error_detail))
    

async def execute_task_workflow(
    task_id: str,
    executable_subtask_ids: set[str],
    websocket_manager: WebSocketManager
) -> TaskResult:
    """Execute the task workflow with real-time status updates."""
    try:
        task = orcs.tasks.get(task_id)
        if not task:
            await websocket_manager.send_message(
                task_id,
                {
                    "type": "SUBTASK_UPDATE",
                    "payload": {
                        "subtask_id": None,
                        "status": TaskStatus.FAILED,
                        "message": f"Task {task_id} not found",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            )
            return None

        # Initial status update
        await websocket_manager.send_message(
            task_id,
            {
                "type": "SUBTASK_UPDATE",
                "payload": {
                    "subtask_id": None,
                    "status": TaskStatus.IN_PROGRESS,
                    "message": f"Starting execution workflow for task: {task_id}",
                    "timestamp": datetime.now().isoformat()
                }
            }
        )

        # Filter executable subtasks
        filtered_task = task.model_copy()
        filtered_task.subtasks = [
            subtask for subtask in task.subtasks 
            if subtask.subtask_id in executable_subtask_ids
        ]

        # Status callback for ORCS
        async def status_callback(
            subtask_id: str, 
            status: TaskStatus, 
            message: str,
            content: Optional[dict] = None  # New optional content parameter
        ):
            await websocket_manager.send_message(
                task_id,
                {
                    "type": "SUBTASK_UPDATE",
                    "payload": {
                        "subtask_id": subtask_id,
                        "status": status,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                        "content": content  # Add content if provided
                    }
                }
            )

        # Begin execution with status updates
        orcs.tasks[task_id] = filtered_task
        result = await orcs.execute_task(filtered_task, status_callback=status_callback)

        # Final status update
        await websocket_manager.send_message(
            task_id,
            {
                "type": "SUBTASK_UPDATE",
                "payload": {
                    "subtask_id": None,
                    "status": result.status,
                    "message": f"Task execution completed: {result.message}",
                    "timestamp": datetime.now().isoformat()
                }
            }
        )

        return result

    except Exception as e:
        error_msg = f"Error in task execution: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        await websocket_manager.send_message(
            task_id,
            {
                "type": "SUBTASK_UPDATE",
                "payload": {
                    "subtask_id": None,
                    "status": TaskStatus.FAILED,
                    "message": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )
        raise

@app.websocket("/api/task-execution/{task_id}")
async def task_execution_websocket(websocket: WebSocket, task_id: str):
    try:
        # Connect new WebSocket
        await websocket_manager.connect(task_id, websocket)
        print(f"\nWebSocket connection established for task: {task_id}")
        
        while True:
            # Wait for messages
            message = await websocket_manager.receive_json(task_id)
            if not message:
                break
                
            print(f"\nReceived message for task {task_id}:", message)
            
            if message["type"] == "START_EXECUTION":
                print(f"\nStarting execution for task {task_id}")
                print("Payload received:", message["payload"])
                
                # Send initial status
                await websocket_manager.send_message(
                    task_id,
                    {
                        "type": "EXECUTION_STATUS",
                        "payload": {
                            "status": TaskStatus.IN_PROGRESS,
                            "message": "Starting task execution workflow"
                        }
                    }
                )
                
                try:
                    # Get executable subtasks
                    executable_subtask_ids = {
                        subtask["subtask_id"] 
                        for subtask in message["payload"]["subtasks"]
                    }
                    print(f"Executable subtasks: {executable_subtask_ids}")
                    
                    # Execute task with WebSocket manager
                    result = await execute_task_workflow(
                        task_id, 
                        executable_subtask_ids,
                        websocket_manager
                    )
                    
                    if result:
                        await websocket_manager.send_message(
                            task_id,
                            {
                                "type": "EXECUTION_STATUS",
                                "payload": {
                                    "status": result.status,
                                    "message": result.message
                                }
                            }
                        )
                        
                except Exception as e:
                    error_msg = f"Error executing task {task_id}: {str(e)}"
                    print(f"\nERROR: {error_msg}")
                    print(f"Traceback: {traceback.format_exc()}")
                    
                    await websocket_manager.send_message(
                        task_id,
                        {
                            "type": "EXECUTION_STATUS",
                            "payload": {
                                "status": TaskStatus.FAILED,
                                "message": error_msg
                            }
                        }
                    )
                    
    except WebSocketDisconnect:
        print(f"\nWebSocket disconnect detected for task: {task_id}")
    except Exception as e:
        print(f"\nUnexpected error in WebSocket connection for task {task_id}:")
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
    finally:
        # Clean up regardless of how we exit
        await websocket_manager.disconnect(task_id)
        print(f"Cleaned up connection for task: {task_id}")
                
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )