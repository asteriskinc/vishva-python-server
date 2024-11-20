from orcs.types import Agent
from vishva.agent_instructions import * 

def transfer_to_selector_agent():
    return SelectorAgent

def transfer_to_planner_agent():
    return PlannerAgent

def transfer_to_creator_agent():
    return CreatorAgent

IntentAgent = Agent(
    name="Intent Agent",
    model="gpt-4o-mini",
    instructions=INTENT_AGENT_INSTRUCTIONS,
    functions=[transfer_to_selector_agent],
    tool_choice="auto",
)

SelectorAgent = Agent(
    name="Selector Agent",
    model="gpt-4o-mini",
    instructions=SELECTOR_AGENT_INSTRUCTIONS,
    functions=[transfer_to_planner_agent, transfer_to_creator_agent],
    tool_choice="auto",
)

CreatorAgent = Agent(
    name="Creator Agent",
    model="gpt-4o-mini",
    instructions=CREATOR_AGENT_INSTRUCTIONS,
    functions=[transfer_to_planner_agent],
    tool_choice="auto",
)

PlannerAgent = Agent(
    name="Planner Agent",
    model="gpt-4o-mini",
    instructions=PLANNER_PLANNER_AGENT_INSTRUCTIONS,
)
