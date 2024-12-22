# server.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn
import uuid
from enum import Enum
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Vishva API")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your Next.js development server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Define models
class AgentCapability(str, Enum):
    LOCATION = "location"
    SEARCH = "search"
    SCHEDULING = "scheduling"
    NAVIGATION = "navigation"
    PAYMENT = "payment"
    COMPARISON = "comparison"
    RECOMMENDATIONS = "recommendations"

class Agent(BaseModel):
    id: str
    name: str
    capabilities: List[AgentCapability]

# Predefined agents
AVAILABLE_AGENTS = [
    Agent(
        id="location_agent",
        name="Location Agent",
        capabilities=[AgentCapability.LOCATION]
    ),
    Agent(
        id="search_agent",
        name="Search Agent",
        capabilities=[AgentCapability.SEARCH, AgentCapability.COMPARISON]
    ),
    Agent(
        id="scheduling_agent",
        name="Scheduling Agent",
        capabilities=[AgentCapability.SCHEDULING]
    ),
    Agent(
        id="navigation_agent",
        name="Navigation Agent",
        capabilities=[AgentCapability.NAVIGATION]
    ),
    Agent(
        id="concierge_agent",
        name="Concierge Agent",
        capabilities=[AgentCapability.RECOMMENDATIONS]
    ),
]

class QueryRequest(BaseModel):
    query: str

class SubTask(BaseModel):
    title: str
    status: str = "pending"
    agent: str
    detail: str
    icon: Optional[str] = None
    category: int  # 1: Direct, 2: Optional
    approved: Optional[bool] = None

class TaskResponse(BaseModel):
    id: str
    query: str
    timestamp: str
    domain: str
    needsClarification: bool
    clarificationPrompt: Optional[str] = None
    subtasks: List[SubTask]

def get_icon_for_capability(capability: AgentCapability) -> str:
    icon_map = {
        AgentCapability.LOCATION: "MapPin",
        AgentCapability.SEARCH: "Search",
        AgentCapability.SCHEDULING: "Timer",
        AgentCapability.NAVIGATION: "Navigation",
        AgentCapability.PAYMENT: "CreditCard",
        AgentCapability.COMPARISON: "Building2",
        AgentCapability.RECOMMENDATIONS: "ShoppingCart",
    }
    return icon_map.get(capability, "Bot")

@app.get("/")
async def read_root():
    return {"status": "healthy", "message": "Vishva API is running"}

@app.post("/api/process-query")
async def process_query(request: QueryRequest):
    try:
        # Create the list of available agents for the prompt
        agent_descriptions = "\n".join([
            f"- {agent.name}: {', '.join([cap.value for cap in agent.capabilities])}"
            for agent in AVAILABLE_AGENTS
        ])
        
        # Make the API call with structured output
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a task planning assistant that breaks down user queries into actionable subtasks."
                },
                {
                    "role": "user",
                    "content": f"""Break down this user query into subtasks:
                    
Query: {request.query}

Available Agents:
{agent_descriptions}

Consider both direct necessary tasks and optional helpful tasks."""
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task_breakdown_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "domain": {
                                "type": "string",
                                "description": "Category of the task (e.g., Entertainment, Travel, Shopping)"
                            },
                            "needsClarification": {
                                "type": "boolean",
                                "description": "Whether clarification is needed from the user"
                            },
                            "clarificationPrompt": {
                                "type": "string",
                                "description": "Question to ask user for clarification if needed"
                            },
                            "subtasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string",
                                            "description": "Name of the subtask"
                                        },
                                        "agent": {
                                            "type": "string",
                                            "description": "Name of the agent to handle this task"
                                        },
                                        "detail": {
                                            "type": "string",
                                            "description": "Description of what will be done (in future tense)"
                                        },
                                        "category": {
                                            "type": "integer",
                                            "enum": [1, 2],
                                            "description": "1: Direct necessary task, 2: Optional helpful task"
                                        }
                                    },
                                    "required": ["title", "agent", "detail", "category"]
                                }
                            }
                        },
                        "required": ["domain", "needsClarification", "subtasks"],
                        "additionalProperties": False
                    }
                }
            }
        )
        
        # Parse the LLM response
        llm_response = json.loads(response.choices[0].message.content)
        
        # Create the task response
        task_response = TaskResponse(
            id=str(uuid.uuid4()),
            query=request.query,
            timestamp="Just now",
            domain=llm_response["domain"],
            needsClarification=llm_response["needsClarification"],
            clarificationPrompt=llm_response.get("clarificationPrompt"),
            subtasks=[]
        )
        
        # Process subtasks and add appropriate icons
        for subtask in llm_response["subtasks"]:
            agent = next((a for a in AVAILABLE_AGENTS if a.name == subtask["agent"]), None)
            if agent and agent.capabilities:
                icon = get_icon_for_capability(agent.capabilities[0])
            else:
                icon = "Bot"
                
            task_response.subtasks.append(SubTask(
                title=subtask["title"],
                agent=subtask["agent"],
                detail=subtask["detail"],
                icon=icon,
                category=subtask["category"]
            ))
        
        return task_response
        
    except Exception as e:
        import traceback
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print("Error processing query:", error_detail)  # For server logs
        raise HTTPException(status_code=500, detail=str(error_detail))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server-v2:app",  # This should match your filename: "{filename}:app"
        host="0.0.0.0",
        port=8000,
        reload=True
    )