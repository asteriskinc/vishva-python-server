# executor_agents.py contains all the mini agents that execute various tasks that they're designated by the Orchestrator or Planner Agents. 
from orcs.types import Agent
from vishva.agent_tools import * 
from vishva.agent_instructions import * 
from vishva.commerce_tools import *



def transfer_to_web_search_agent():
    return WebSearchAgent

def transfer_to_movie_agent():
    return MovieAgent

def transfer_to_directions_agent():
    return DirectionsAgent

def transfer_to_commerce_agent():
    return CommerceAgent


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


CommerceAgent = Agent(
    name="Commerce Agent",
    model="gpt-4o-mini",
    instructions=COMMERCE_AGENT_INSTRUCTIONS,
    functions=[
        transfer_to_web_search_agent,
        transfer_to_directions_agent,
        retrieve_page_content,
        analyze_shopping_results,
        compare_product_pages
    ],
)