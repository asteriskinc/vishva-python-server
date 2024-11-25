import json
from typing import Any, Dict, List, Optional, Callable
from typing_extensions import Literal
from orcs.types import Agent
from vishva.agent_instructions import *
from vishva.executor_agents import (
    AccommodationAgent,
    ActivityAgent,
    DirectionsAgent,
    FlightSearchAgent,
    MovieAgent,
    WebSearchAgent,
)
from dataclasses import dataclass


def transfer_to_selector_agent():
    return SelectorAgent


def transfer_to_planner_agent():
    return PlannerAgent


def transfer_to_creator_agent():
    return CreatorAgent

def transfer_to_starter_agent():
    return StarterAgent


def create_transfer_functions(agents: List[Agent]) -> List[Callable]:
    """
    Creates transfer functions for each agent that can be used by the starter agent.

    Args:
        agents: List of Agent objects to create transfer functions for

    Returns:
        List of transfer functions
    """
    transfer_functions = []

    for agent in agents:
        # Create a lambda that captures the agent instance
        transfer_func = lambda _: agent  # Default argument to capture current agent
        transfer_func.__name__ = f"transfer_to_{agent.name.lower().replace(' ', '_')}"

        # Add docstring
        transfer_func.__doc__ = f"""
        Transfer control to the {agent.name}.
        
        Returns:
            Agent: The {agent.name} instance
        """

        transfer_functions.append(transfer_func)
        transfer_functions.append(transfer_to_starter_agent)

    return transfer_functions


def get_agents_for_execution(
    agent_names: List[
        Literal[
            "WebSearchAgent",
            "MovieAgent",
            "DirectionsAgent",
            "FlightSearchAgent",
            "AccommodationAgent",
            "ActivityAgent",
        ]
    ]
) -> List[Agent]:
    """
    Takes a list of agent names and returns the corresponding agent objects.

    Args:
        agent_names: List of agent names to execute

    Returns:
        List of Agent objects corresponding to the requested names
    """
    agent_map = {
        "WebSearchAgent": WebSearchAgent,
        "MovieAgent": MovieAgent,
        "DirectionsAgent": DirectionsAgent,
        "FlightSearchAgent": FlightSearchAgent,
        "AccommodationAgent": AccommodationAgent,
        "ActivityAgent": ActivityAgent,
    }

    agents = []
    for name in agent_names:
        if name in agent_map:
            agents.append(agent_map[name])

    print(f"Retrieved {len(agents)} agents: {agents} for agent_names: {agent_names}")

    # Create transfer functions for these agents
    transfer_functions = create_transfer_functions(agents)

    # Add transfer functions to the starter agent
    StarterAgent.functions.extend(transfer_functions)

    return agents


@dataclass
class AgentSpec:
    """Specification for creating a new Agent."""

    name: str
    instructions: str
    functions: Optional[List[callable]] = None
    tool_choice: str = "auto"
    model: str = "gpt-4o-mini"


def create_agents(agent_specs: List[Dict[str, Any]]) -> List[Agent]:
    """
    Creates Agent objects based on specifications provided by the CreatorAgent.

    Args:
        agent_specs: List of AgentSpec objects defining the agents to create

    Returns:
        List of created Agent objects
    """
    print(f"Creating {len(agent_specs)} agents from specs: {agent_specs}")
    agents = []
    for spec in agent_specs:
        agent = Agent(
            name=spec["name"],
            model=spec["model"] if "model" in spec else "gpt-4o-mini",
            instructions=spec["instructions"],
            functions=spec["functions"] if "functions" in spec else [],
            tool_choice=spec["tool_choice"] if "tool_choice" in spec else "auto",
        )
        agents.append(agent)
    print(f"Created {len(agents)} agents from {len(agent_specs)} specs: {agents}")
    return agents


IntentAgent = Agent(
    name="Intent Agent",
    model="gpt-4o-mini",
    instructions=INTENT_AGENT_INSTRUCTIONS,
    functions=[transfer_to_selector_agent],
    tool_choice="required",
)

SelectorAgent = Agent(
    name="Selector Agent",
    model="gpt-4o",
    instructions=SELECTOR_AGENT_INSTRUCTIONS,
    functions=[
        transfer_to_planner_agent,
        get_agents_for_execution,
    ],
    tool_choice="required",
)

CreatorAgent = Agent(
    name="Creator Agent",
    model="gpt-4o",
    instructions=CREATOR_AGENT_INSTRUCTIONS,
    functions=[transfer_to_planner_agent],
    tool_choice="required",
)

PlannerAgent = Agent(
    name="Planner Agent",
    model="gpt-4o-mini",
    instructions=PLANNER_PLANNER_AGENT_INSTRUCTIONS,
    functions=[transfer_to_starter_agent],
)

StarterAgent = Agent(
    name="Starter Agent",
    model="gpt-4o-mini",
    instructions=STARTER_AGENT_INSTRUCTIONS,
    parallel_tool_calls=False,
)
