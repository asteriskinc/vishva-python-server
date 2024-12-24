from typing import List
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from enum import Enum
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

# Load environment variables
load_dotenv()

# Initialize Rich console
console = Console()

class AgentCapability(str, Enum):
    LOCATION = "location"
    SEARCH = "search"
    SCHEDULING = "scheduling"
    NAVIGATION = "navigation"
    PAYMENT = "payment"
    COMPARISON = "comparison"
    RECOMMENDATIONS = "recommendations"

class ServerAgent(BaseModel):
    id: str
    name: str
    capabilities: List[AgentCapability]

# Predefined agents from server-v2.py
AVAILABLE_AGENTS = [
    ServerAgent(
        id="location_agent",
        name="Location Agent",
        capabilities=[AgentCapability.LOCATION]
    ),
    ServerAgent(
        id="search_agent",
        name="Search Agent",
        capabilities=[AgentCapability.SEARCH, AgentCapability.COMPARISON]
    ),
    ServerAgent(
        id="scheduling_agent",
        name="Scheduling Agent",
        capabilities=[AgentCapability.SCHEDULING]
    ),
    ServerAgent(
        id="navigation_agent",
        name="Navigation Agent",
        capabilities=[AgentCapability.NAVIGATION]
    ),
    ServerAgent(
        id="concierge_agent",
        name="Concierge Agent",
        capabilities=[AgentCapability.RECOMMENDATIONS]
    ),
]

class SubTaskBreakdown(BaseModel):
    title: str
    agent: str
    detail: str
    category: int  # 1: Direct, 2: Optional

class TaskBreakdown(BaseModel):
    domain: str
    needsClarification: bool
    clarificationPrompt: str | None = None
    subtasks: List[SubTaskBreakdown]

def get_task_breakdown(query: str, client: OpenAI) -> TaskBreakdown:
    """Get task breakdown using the OpenAI API"""
    
    # Create the list of available agents for the prompt
    agent_descriptions = "\n".join([
        f"- {agent.name}: {', '.join([cap.value for cap in agent.capabilities])}"
        for agent in AVAILABLE_AGENTS
    ])
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a task planning assistant that breaks down user queries into actionable subtasks."
            },
            {
                "role": "user",
                "content": f"""Break down this user query into subtasks:
                
Query: {query}

Available Agents:
{agent_descriptions}

Break this query down into:
1. Direct necessary tasks (category 1)
2. Optional helpful tasks (category 2)

For each task, provide:
- A clear title
- Which agent should handle it
- Detailed description of what will be done"""
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
                        "description": "Category of the task"
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
                                "title": {"type": "string"},
                                "agent": {"type": "string"},
                                "detail": {"type": "string"},
                                "category": {
                                    "type": "integer",
                                    "enum": [1, 2]
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
    
    # Debug: Print raw response
    raw_content = response.choices[0].message.content
    # console.print("\n[bold cyan]Raw API Response:[/bold cyan]")
    # console.print(raw_content)
    
    # Parse JSON response
    result = json.loads(raw_content)
    # console.print("\n[bold cyan]Parsed JSON:[/bold cyan]")
    # console.print(json.dumps(result, indent=2))
    
    # Create TaskBreakdown object
    try:
        return TaskBreakdown(**result)
    except Exception as e:
        console.print(f"\n[bold red]Error creating TaskBreakdown:[/bold red]")
        console.print(f"Result keys: {result.keys()}")
        console.print(f"Result structure: {json.dumps(result, indent=2)}")
        raise

def display_task_breakdown(breakdown: TaskBreakdown):
    """Display the task breakdown in a formatted way"""
    console.print("\n[bold blue]Task Breakdown Results[/bold blue]")
    
    # Display domain and clarification info
    console.print(Panel(f"[yellow]Domain:[/yellow] {breakdown.domain}"))
    
    if breakdown.needsClarification:
        console.print(Panel(
            f"[red]Clarification Needed:[/red]\n{breakdown.clarificationPrompt}",
            title="Clarification Required"
        ))
    
    # Display required tasks
    console.print("\n[bold green]Required Tasks:[/bold green]")
    for task in [t for t in breakdown.subtasks if t.category == 1]:
        console.print(Panel(
            f"[cyan]Title:[/cyan] {task.title}\n"
            f"[cyan]Agent:[/cyan] {task.agent}\n"
            f"[cyan]Details:[/cyan] {task.detail}",
            title="Direct Task",
            border_style="green"
        ))
    
    # Display optional tasks
    console.print("\n[bold yellow]Optional Tasks:[/bold yellow]")
    for task in [t for t in breakdown.subtasks if t.category == 2]:
        console.print(Panel(
            f"[cyan]Title:[/cyan] {task.title}\n"
            f"[cyan]Agent:[/cyan] {task.agent}\n"
            f"[cyan]Details:[/cyan] {task.detail}",
            title="Optional Task",
            border_style="yellow"
        ))

def main():
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Example queries to test
    queries = [
        "I want to watch a movie this weekend. Can you help me find good options and theaters nearby?",
        "I need to buy a birthday gift for my friend who likes photography.",
        "Plan a dinner date for tomorrow evening."
    ]
    
    # Test each query
    for i, query in enumerate(queries, 1):
        console.print(f"\n[bold purple]Testing Query {i}:[/bold purple] {query}")
        try:
            breakdown = get_task_breakdown(query, client)
            display_task_breakdown(breakdown)
        except Exception as e:
            console.print(f"[bold red]Error processing query:[/bold red] {str(e)}")
        
        if i < len(queries):
            input("\nPress Enter to continue to next query...")

if __name__ == "__main__":
    main()