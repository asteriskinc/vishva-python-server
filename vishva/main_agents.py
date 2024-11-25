# main_agents.py contains the agents that manage every other agent. 
from orcs.types import Agent
from vishva.agent_tools import * 
from vishva.executor_agents import * 
from vishva.agent_instructions import * 

def transfer_to_orchestrator_agent():
    return OrchestratorAgent

OrchestratorAgent = Agent(
    name="Orchestrator Agent",
    model="gpt-4o",
    instructions=ORCHESTRATOR_AGENT_INSTRUCTIONS_2,
    functions=[transfer_to_web_search_agent, transfer_to_movie_agent, transfer_to_directions_agent, transfer_to_commerce_agent],
    parallel_tool_calls=True,
)

def transfer_to_planner_agent():
    return PlannerAgent

PlannerAgent = Agent(
    name="Planner Agent",
    model="gpt-4o",
    instructions=PLANNER_AGENT_INSTRUCTIONS_2,
    functions=[transfer_to_orchestrator_agent, perform_web_search],
    parallel_tool_calls=True,
)