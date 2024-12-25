# orcs-v2/agents.py

from orc_types import Agent

PlannerAgent = Agent(
    name="Planner",
    model="gpt-4o-mini",
    instructions="You are a task planner that breaks down user queries into subtasks.",
    tools={}
)

