# execution_agents.py
from pydantic import BaseModel
from .orcs_types import Agent, DictList
from .tools.web_tools import web_search, get_distance_matrix, get_directions

# Response schemas for different agent types
class LocationInfo(BaseModel):
    address: str
    coordinates: DictList
    place_id: str
    additional_info: DictList

class LocationResponse(BaseModel):
    locations: list[LocationInfo]
    search_radius: float
    search_query: str

class Schedule(BaseModel):
    event_time: str
    duration: int
    location: str
    participants: list[str]
    notes: str

class SchedulingResponse(BaseModel):
    schedule: Schedule
    alternatives: list[Schedule]
    conflicts: list[str]

class MovieShowtime(BaseModel):
    movie_title: str
    theater_name: str
    theater_location: str
    datetime: str
    price: float
    available_seats: int
    booking_link: str

class MovieBookingResponse(BaseModel):
    showtimes: list[MovieShowtime]
    selected_showtime: MovieShowtime
    booking_status: str
    payment_options: list[str]

class Restaurant(BaseModel):
    name: str
    cuisine: str
    price_range: str
    rating: float
    location: str
    available_times: list[str]
    menu_link: str

class DiningResponse(BaseModel):
    restaurants: list[Restaurant]
    selected_restaurant: Restaurant
    booking_status: str
    special_requests: str

class NavigationResponse(BaseModel):
    route: str
    distance: str
    duration: str
    traffic_info: str
    alternative_routes: list[str]

# Define specialized agents for specific use cases

# Movie Booking Agent
MovieBookingAgent = Agent(
    name="Movie Booking Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a specialized movie booking assistant. Your role is to:
1. Search for and compare movie showtimes across theaters
2. Consider user preferences for movie genre, timing, and location
3. Check theater amenities and seating availability
4. Handle booking processes and payment options

Use available tools to:
- Search for movie information and reviews
- Find nearby theaters
- Calculate travel times to theaters
- Compare prices and showtimes

Always consider:
- Movie ratings and reviews
- Theater distance and accessibility
- Show timing preferences
- Seat availability
- IMAX/3D/special format options""",
    tools={
        "web_search": web_search,
        "get_distance_matrix": get_distance_matrix,
        "get_directions": get_directions
    },
    response_format=MovieBookingResponse
)

# Restaurant Booking Agent
RestaurantBookingAgent = Agent(
    name="Restaurant Booking Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a specialized restaurant booking assistant. Your role is to:
1. Find and evaluate restaurants based on user preferences
2. Check availability and make reservations
3. Consider dietary restrictions and special occasions
4. Provide menu information and recommendations

Use available tools to:
- Search for restaurant information and reviews
- Calculate distance and travel time
- Check opening hours and availability
- Find and compare menus

Always consider:
- Cuisine preferences
- Dietary restrictions
- Price range
- Location and accessibility
- Special occasion requirements
- Group size accommodations""",
    tools={
        "web_search": web_search,
        "get_distance_matrix": get_distance_matrix,
        "get_directions": get_directions
    },
    response_format=DiningResponse
)

# Event Planning Agent
EventPlanningAgent = Agent(
    name="Event Planning Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are an event planning specialist. Your role is to:
1. Find and evaluate event venues and services
2. Create schedules and timelines
3. Coordinate with multiple vendors and services
4. Handle RSVPs and guest management

Use available tools to:
- Search for venue information
- Calculate travel times and accessibility
- Research vendors and services
- Compare prices and availability

Always consider:
- Event type and size
- Budget constraints
- Location accessibility
- Vendor availability
- Weather considerations
- Backup plans and alternatives""",
    tools={
        "web_search": web_search,
        "get_distance_matrix": get_distance_matrix,
        "get_directions": get_directions
    },
    response_format=SchedulingResponse
)

# Transportation Agent
TransportationAgent = Agent(
    name="Transportation Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a transportation and navigation specialist. Your role is to:
1. Plan optimal routes for various transportation modes
2. Compare different transportation options
3. Consider traffic patterns and delays
4. Provide real-time navigation assistance

Use available tools to:
- Calculate routes and travel times
- Search for transportation services
- Check traffic conditions
- Find parking options

Always consider:
- Multiple transport modes
- Traffic conditions
- Cost comparisons
- Accessibility needs
- Time constraints
- Weather impact""",
    tools={
        "web_search": web_search,
        "get_distance_matrix": get_distance_matrix,
        "get_directions": get_directions
    },
    response_format=NavigationResponse
)

# Export all agents
EXECUTION_AGENTS = {
    "Movie Booking Agent": MovieBookingAgent,
    "Restaurant Booking Agent": RestaurantBookingAgent,
    "Event Planning Agent": EventPlanningAgent,
    "Transportation Agent": TransportationAgent
}