# Executor Agents Defined here 
from orcs.types import Agent
from vishva.agent_tools import * 
from vishva.agent_instructions import * 

def transfer_to_web_search_agent():
    return WebSearchAgent


def transfer_to_movie_agent():
    return MovieAgent

def transfer_to_directions_agent():
    return DirectionsAgent

WebSearchAgent = Agent(
    name="Web Search Agent",
    model="gpt-4o-mini",
    instructions=WEB_AGENT_INSTRUCTIONS,
    functions=[retrieve_url_content, perform_web_search],
    parallel_tool_calls=True,
)

MovieAgent = Agent(
    name="Movie Agent",
    model="gpt-4o-mini",
    instructions=MOVIE_AGENT_INSTRUCTIONS,
    functions=[perform_web_search, retrieve_url_content, transfer_to_directions_agent],
)


DirectionsAgent = Agent(
    name="Directions Agent",
    model="gpt-4o-mini",
    instructions=DIRECTIONS_AGENT_INSTRUCTIONS,
    functions=[get_driving_directions],
)

