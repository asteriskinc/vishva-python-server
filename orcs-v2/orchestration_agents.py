# orchestration_agents.py

# This file will contain all the agents that will be used to orchestrate the tasks including the planner agent, and the dependency determination agent. 

# The planner agent will be responsible for taking the user query and converting it into a task object. 
# The dependency determination agent will be responsible for determining the dependencies between the subtasks and the task. 

from typing import Type
from pydantic import BaseModel
from .types import Agent, AgentTool

# Define the Planner Agent
PlannerAgent = Agent(
    name="Planner Agent",
    model="gpt-4o-mini",
    instructions="""You are a task planning assistant that breaks down user queries into actionable subtasks.
    
Your role is to:
1. Understand the user's query and its broader implications
2. Break down the task into logical subtasks
3. Assign appropriate agents to each subtask
4. Determine if any clarification is needed from the user

For each subtask, consider:
- Is it directly necessary (category 1) or optionally helpful (category 2)?
- Which agent is best suited for this specific subtask?
- What specific actions will be taken?

Available Agents and their capabilities:
- Location Agent: location-based searches and queries
- Search Agent: web searches and comparisons
- Scheduling Agent: time-based tasks and scheduling
- Navigation Agent: routing and transportation
- Concierge Agent: recommendations and personalized suggestions""",
    response_format={
        "type": "json_schema",
        "json_schema": {
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
            "required": ["domain", "needsClarification", "subtasks"]
        }
    }
)

# Define the Dependency Determination Agent
DependencyAgent = Agent(
    name="Dependency Agent",
    model="gpt-4o-mini",
    instructions="""You are a dependency analysis agent that determines the relationships and dependencies between subtasks.

Your role is to:
1. Analyze the provided task and its subtasks
2. Identify which subtasks depend on others
3. Specify what data needs to be passed between dependent tasks
4. Create a logical execution order

Consider:
- Which tasks must be completed before others can begin?
- What specific data or information needs to flow between tasks?
- Are there any parallel execution opportunities?
- What's the critical path for task completion?

You will receive the complete task information including all subtasks and their details.
You must determine the dependencies and specify what data fields are required between dependent tasks.""",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "type": "object",
            "properties": {
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dependent_subtask_id": {
                                "type": "string",
                                "description": "ID of the subtask that depends on another"
                            },
                            "required_subtask_id": {
                                "type": "string",
                                "description": "ID of the subtask that must be completed first"
                            },
                            "required_data": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of data fields that must be present in the required subtask's result"
                            },
                            "dependency_reason": {
                                "type": "string",
                                "description": "Explanation of why this dependency exists"
                            }
                        },
                        "required": ["dependent_subtask_id", "required_subtask_id", "required_data"]
                    }
                }
            },
            "required": ["dependencies"]
        }
    }
)