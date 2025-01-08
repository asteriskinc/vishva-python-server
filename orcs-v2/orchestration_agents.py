# orchestration_agents.py
from pydantic import BaseModel
from orcs_types import Agent

# Define response format for Planner Agent
class SubtaskSchema(BaseModel):
    title: str
    agent: str
    detail: str
    category: int  # 1: Direct necessary task, 2: Optional helpful task

class PlannerResponse(BaseModel):
    domain: str
    needsClarification: bool
    clarificationPrompt: str
    subtasks: list[SubtaskSchema]

# Define response format for Dependency Agent
class SubtaskDependency(BaseModel):
    subtask_id: str
    depends_on: str  # ID of the subtask this depends on

class DependencyResponse(BaseModel):
    subtask_dependencies: list[SubtaskDependency]

# Define the Planner Agent
PlannerAgent = Agent(
    name="Planner Agent",
    model="gpt-4o-mini-2024-07-18",
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
    response_format=PlannerResponse
)

# Define the Dependency Determination Agent
DependencyAgent = Agent(
    name="Dependency Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a dependency analysis agent that determines the relationships between subtasks.

Your role is to:
1. Analyze the provided task and its subtasks
2. For each subtask, determine if it depends on the completion of any other subtask
3. Create a logical execution order

For example:
- If suggesting restaurants near a movie theater, that subtask would depend on the movie theater location being determined first
- If booking a table at a restaurant, that would depend on the restaurant being selected first
- If calculating travel time to a venue, that would depend on the venue being chosen first

For each subtask, you should specify:
- The subtask_id (provided in the input)
- The ID of another subtask it depends on (if any)

You will receive a list of subtasks with their IDs, titles, and details. Return a list of dependencies for each subtask.""",
    response_format=DependencyResponse
)