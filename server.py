# server.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import json
from typing import Dict
from orcs.core import ORCS
from orcs.execution_agents import EXECUTION_AGENTS
from orcs.orcs_types import Task, TaskStatus
import asyncio

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
                # For now, just acknowledge receipt
                await websocket.send_json({
                    "type": "EXECUTION_STATUS",
                    "payload": {
                        "status": "in_progress",
                        "message": "Task execution started"
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