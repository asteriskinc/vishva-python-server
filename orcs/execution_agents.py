# execution_agents.py
from pydantic import BaseModel
from .orcs_types import Agent, DictList
from typing import Optional, Dict, Any
from .tools import AVAILABLE_TOOLS

class BaseAgentResponse(BaseModel):
    """Base response format that all agent responses must inherit from"""
    use_tool: bool
    tool_name: Optional[str]
    tool_params: Optional[Dict[str, Any]]

# Response schemas for different agent types
class LocationInfo(BaseModel):
    address: str
    coordinates: DictList
    place_id: str
    additional_info: DictList

class LocationResponse(BaseAgentResponse):
    locations: list[LocationInfo]
    search_radius: float
    search_query: str

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    timestamp: str
    relevance_score: float

class SearchResponse(BaseAgentResponse):
    results: list[SearchResult]
    query: str
    total_results: int
    filtered_results: int

class Schedule(BaseModel):
    event_time: str
    duration: int
    location: str
    participants: list[str]
    notes: str

class SchedulingResponse(BaseAgentResponse):
    schedule: Schedule
    alternatives: list[Schedule]
    conflicts: list[str]

class NavigationStep(BaseModel):
    instruction: str
    distance: float
    duration: float
    mode: str
    additional_info: DictList

class NavigationResponse(BaseAgentResponse):
    steps: list[NavigationStep]
    total_distance: float
    total_duration: float
    start_location: str
    end_location: str
    transport_mode: str

class Recommendation(BaseModel):
    title: str
    category: str
    rating: float
    price_range: str
    description: str
    location: str
    availability: str
    additional_info: DictList

class ConciergeResponse(BaseAgentResponse):
    recommendations: list[Recommendation]
    search_criteria: DictList
    total_options: int

# Define the Location Agent
LocationAgent = Agent(
    name="Location Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a location-based search specialist. Your role is to:
1. Process location-related queries accurately
2. Find and validate physical locations
3. Provide detailed location information including coordinates
4. Consider context and user preferences when searching
5. Handle both specific addresses and general area searches

You have access to these tools:
- get_distance: Get distance and duration between two locations
- get_directions: Generate driving directions between locations

Always provide:
- Full address information
- Coordinates when available
- Relevant place IDs or references
- Additional context about the location""",
    response_format=LocationResponse,
    tools=[t for t in AVAILABLE_TOOLS if t.name in ["get_distance", "get_directions"]]
)

# Define the Search Agent
SearchAgent = Agent(
    name="Search Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a web search and comparison specialist. Your role is to:
1. Execute detailed web searches based on user queries
2. Filter and rank results by relevance
3. Compare options across multiple sources
4. Validate information from multiple sources
5. Provide structured, actionable search results

You have access to these tools:
- web_search: Perform web searches and get results
- url_content: Retrieve and parse content from URLs

For each search result, include:
- Title and URL
- Relevant snippet or summary
- Source credibility assessment
- Timestamp of information
- Relevance score""",
    response_format=SearchResponse,
    tools=[t for t in AVAILABLE_TOOLS if t.name in ["web_search", "url_content"]]
)

# Define the Scheduling Agent
SchedulingAgent = Agent(
    name="Scheduling Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a scheduling and time management specialist. Your role is to:
1. Process time-based requests and scheduling needs
2. Check availability and conflicts
3. Suggest optimal timing options
4. Consider duration and buffer times
5. Account for location and travel time when relevant

You have access to these tools:
- get_distance: Get distance and duration between locations to help with timing

For each scheduling task:
- Validate date and time formats
- Check for scheduling conflicts
- Provide alternative options when needed
- Include relevant location details
- Note any specific requirements or constraints""",
    response_format=SchedulingResponse,
    tools=[t for t in AVAILABLE_TOOLS if t.name in ["get_distance"]]
)

# Define the Navigation Agent
NavigationAgent = Agent(
    name="Navigation Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a navigation and routing specialist. Your role is to:
1. Plan optimal routes between locations
2. Consider multiple transportation modes
3. Account for traffic and timing
4. Provide turn-by-turn directions
5. Calculate accurate travel times and distances

You have access to these tools:
- get_distance: Get distance and duration between locations
- get_directions: Generate driving directions with different transport modes

For each navigation request:
- Break down into clear steps
- Include distance and duration for each step
- Specify transport modes
- Note any potential issues or alternatives
- Consider real-time factors when possible""",
    response_format=NavigationResponse,
    tools=[t for t in AVAILABLE_TOOLS if t.name in ["get_distance", "get_directions"]]
)

# Define the Concierge Agent
ConciergeAgent = Agent(
    name="Concierge Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a recommendations and personalization specialist. Your role is to:
1. Understand user preferences and requirements
2. Provide tailored recommendations
3. Consider multiple factors (price, rating, availability)
4. Offer alternatives and options
5. Include relevant details for decision-making

You have access to these tools:
- web_search: Search for places and recommendations
- url_content: Get detailed information about places
- get_distance: Check distances to recommended places

For each recommendation:
- Include comprehensive details
- Provide ratings and reviews when available
- Note availability and constraints
- Consider user context and preferences
- Offer multiple options when appropriate""",
    response_format=ConciergeResponse,
    tools=[t for t in AVAILABLE_TOOLS if t.name in ["web_search", "url_content", "get_distance"]]
)

# Export all agents
EXECUTION_AGENTS = {
    "Location Agent": LocationAgent,
    "Search Agent": SearchAgent,
    "Scheduling Agent": SchedulingAgent,
    "Navigation Agent": NavigationAgent,
    "Concierge Agent": ConciergeAgent
}