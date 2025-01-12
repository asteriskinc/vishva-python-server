# server.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import json

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

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )