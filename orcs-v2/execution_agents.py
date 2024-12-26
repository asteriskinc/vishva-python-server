# orcs-v2/execution_agents.py
# NOTE: This is a placeholder file for the execution agents. We'll add proper agents soon. 
from typing import List, Optional, Dict
from pydantic import BaseModel
from orcs_types import Agent

# Response schemas for different agent types
class LocationInfo(BaseModel):
    address: str
    coordinates: Dict[str, float]
    place_id: Optional[str] = None
    additional_info: Optional[Dict[str, str]] = None

class LocationResponse(BaseModel):
    locations: List[LocationInfo]
    search_radius: Optional[float] = None
    search_query: str

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    timestamp: str
    relevance_score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total_results: int
    filtered_results: Optional[int] = None

class Schedule(BaseModel):
    event_time: str
    duration: Optional[int] = None  # in minutes
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    notes: Optional[str] = None

class SchedulingResponse(BaseModel):
    schedule: Schedule
    alternatives: Optional[List[Schedule]] = None
    conflicts: Optional[List[str]] = None

class NavigationStep(BaseModel):
    instruction: str
    distance: float
    duration: float
    mode: str
    additional_info: Optional[Dict[str, str]] = None

class NavigationResponse(BaseModel):
    steps: List[NavigationStep]
    total_distance: float
    total_duration: float
    start_location: str
    end_location: str
    transport_mode: str

class Recommendation(BaseModel):
    title: str
    category: str
    rating: float
    price_range: Optional[str] = None
    description: str
    location: Optional[str] = None
    availability: Optional[str] = None
    additional_info: Optional[Dict[str, str]] = None

class ConciergeResponse(BaseModel):
    recommendations: List[Recommendation]
    search_criteria: Dict[str, str]
    total_options: int

# Define the Location Agent
LocationAgent = Agent(
    name="Location Agent",
    model="gpt-4o-mini",
    instructions="""You are a location-based search specialist. Your role is to:
1. Process location-related queries accurately
2. Find and validate physical locations
3. Provide detailed location information including coordinates
4. Consider context and user preferences when searching
5. Handle both specific addresses and general area searches

Always provide:
- Full address information
- Coordinates when available
- Relevant place IDs or references
- Additional context about the location""",
    response_format=LocationResponse
)

# Define the Search Agent
SearchAgent = Agent(
    name="Search Agent",
    model="gpt-4o-mini",
    instructions="""You are a web search and comparison specialist. Your role is to:
1. Execute detailed web searches based on user queries
2. Filter and rank results by relevance
3. Compare options across multiple sources
4. Validate information from multiple sources
5. Provide structured, actionable search results

For each search result, include:
- Title and URL
- Relevant snippet or summary
- Source credibility assessment
- Timestamp of information
- Relevance score""",
    response_format=SearchResponse
)

# Define the Scheduling Agent
SchedulingAgent = Agent(
    name="Scheduling Agent",
    model="gpt-4o-mini",
    instructions="""You are a scheduling and time management specialist. Your role is to:
1. Process time-based requests and scheduling needs
2. Check availability and conflicts
3. Suggest optimal timing options
4. Consider duration and buffer times
5. Account for location and travel time when relevant

For each scheduling task:
- Validate date and time formats
- Check for scheduling conflicts
- Provide alternative options when needed
- Include relevant location details
- Note any specific requirements or constraints""",
    response_format=SchedulingResponse
)

# Define the Navigation Agent
NavigationAgent = Agent(
    name="Navigation Agent",
    model="gpt-4o-mini",
    instructions="""You are a navigation and routing specialist. Your role is to:
1. Plan optimal routes between locations
2. Consider multiple transportation modes
3. Account for traffic and timing
4. Provide turn-by-turn directions
5. Calculate accurate travel times and distances

For each navigation request:
- Break down into clear steps
- Include distance and duration for each step
- Specify transport modes
- Note any potential issues or alternatives
- Consider real-time factors when possible""",
    response_format=NavigationResponse
)

# Define the Concierge Agent
ConciergeAgent = Agent(
    name="Concierge Agent",
    model="gpt-4o-mini",
    instructions="""You are a recommendations and personalization specialist. Your role is to:
1. Understand user preferences and requirements
2. Provide tailored recommendations
3. Consider multiple factors (price, rating, availability)
4. Offer alternatives and options
5. Include relevant details for decision-making

For each recommendation:
- Include comprehensive details
- Provide ratings and reviews when available
- Note availability and constraints
- Consider user context and preferences
- Offer multiple options when appropriate""",
    response_format=ConciergeResponse
)

# Export all agents
EXECUTION_AGENTS = {
    "Location Agent": LocationAgent,
    "Search Agent": SearchAgent,
    "Scheduling Agent": SchedulingAgent,
    "Navigation Agent": NavigationAgent,
    "Concierge Agent": ConciergeAgent
}