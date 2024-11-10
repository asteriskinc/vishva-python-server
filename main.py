# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq import Queue
from typing import Dict, Optional
import json
import uuid
from datetime import datetime
from pydantic import BaseModel

from .utils.context import get_user_context
from .agents import (
    intent_agent,
    movie_agent,
    navigation_agent,
    theaters_agent
)

app = FastAPI(title="Vishva Search API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis and RQ
redis_conn = Redis(host='localhost', port=6379, db=0)
task_queue = Queue(connection=redis_conn)

class SearchRequest(BaseModel):
    query: str
    user_context: Optional[Dict] = None

def process_agent_response(
    response_chunks,
    task_id: str,
    agent_type: str,
    redis_conn: Redis
) -> Dict:
    """Process streaming response from an agent and update task state"""
    latest_response = None
    
    for chunk in response_chunks:
        if "content" in chunk and chunk["content"]:
            try:
                # Try to parse as JSON
                content = json.loads(chunk["content"])
                if isinstance(content, dict) and "type" in content:
                    # Update task state with latest content
                    task_state = json.loads(redis_conn.get(f"task:{task_id}") or "{}")
                    
                    # Initialize task state if empty
                    if not task_state:
                        task_state = {
                            "id": task_id,
                            "status": "processing",
                            "agents": [],
                            "last_updated": datetime.utcnow().isoformat()
                        }
                    
                    # Update or add agent response
                    updated = False
                    for i, agent in enumerate(task_state["agents"]):
                        if agent["type"] == content["type"]:
                            task_state["agents"][i] = content
                            updated = True
                            break
                    
                    if not updated:
                        task_state["agents"].append(content)
                    
                    task_state["last_updated"] = datetime.utcnow().isoformat()
                    redis_conn.set(f"task:{task_id}", json.dumps(task_state))
                    latest_response = content
                    
            except json.JSONDecodeError:
                # Handle non-JSON content
                pass
                
    return latest_response

def process_search_query(task_id: str, query: str, user_context: Optional[Dict] = None):
    """Background task to process search query through agents"""
    from orcs import Orcs
    
    client = Orcs()
    context = user_context or get_user_context()
    messages = [{"role": "user", "content": query}]
    
    try:
        # Initialize task state
        redis_conn.set(
            f"task:{task_id}",
            json.dumps({
                "id": task_id,
                "status": "processing",
                "agents": [],
                "last_updated": datetime.utcnow().isoformat()
            })
        )
        
        # Start with intent agent
        intent_response = client.run(
            agent=intent_agent,
            messages=messages,
            context_variables=context,
            stream=True
        )
        
        intent_result = process_agent_response(
            intent_response,
            task_id,
            "intent",
            redis_conn
        )
        
        if not intent_result:
            raise Exception("Intent agent failed to provide valid response")
        
        # Get next agents to process
        next_agents = intent_result.get("content", {}).get("next_agents", [])
        
        # Process with each required agent
        for agent_type in next_agents:
            if agent_type == "movie":
                movie_response = client.run(
                    agent=movie_agent,
                    messages=messages,
                    context_variables=context,
                    stream=True
                )
                movie_result = process_agent_response(
                    movie_response,
                    task_id,
                    "movie",
                    redis_conn
                )
                
                # Update messages with movie results
                if movie_result:
                    messages.append({
                        "role": "assistant",
                        "content": json.dumps(movie_result)
                    })
                    
                    # Check if theaters search is needed
                    if movie_result.get("content", {}).get("recommendations", {}).get("theaters_nearby"):
                        theaters_response = client.run(
                            agent=theaters_agent,
                            messages=messages,
                            context_variables=context,
                            stream=True
                        )
                        theaters_result = process_agent_response(
                            theaters_response,
                            task_id,
                            "theaters",
                            redis_conn
                        )
                        
                        if theaters_result:
                            messages.append({
                                "role": "assistant",
                                "content": json.dumps(theaters_result)
                            })
            
            elif agent_type == "navigation":
                navigation_response = client.run(
                    agent=navigation_agent,
                    messages=messages,
                    context_variables=context,
                    stream=True
                )
                navigation_result = process_agent_response(
                    navigation_response,
                    task_id,
                    "navigation",
                    redis_conn
                )
        
        # Mark task as completed
        task_state = json.loads(redis_conn.get(f"task:{task_id}"))
        task_state["status"] = "completed"
        task_state["last_updated"] = datetime.utcnow().isoformat()
        redis_conn.set(f"task:{task_id}", json.dumps(task_state))
        
    except Exception as e:
        # Update task state with error
        redis_conn.set(
            f"task:{task_id}",
            json.dumps({
                "id": task_id,
                "status": "error",
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            })
        )
        raise

@app.post("/api/search")
async def create_search(request: SearchRequest):
    """Create a new search task"""
    task_id = str(uuid.uuid4())
    
    # Enqueue the search task
    task_queue.enqueue(
        process_search_query,
        task_id,
        request.query,
        request.user_context,
        job_id=task_id
    )
    
    return {"task_id": task_id}

@app.get("/api/search/{task_id}")
async def get_search_status(task_id: str):
    """Get the current status of a search task"""
    task_state = redis_conn.get(f"task:{task_id}")
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")
    return json.loads(task_state)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)