# app/agents/theaters.py
from orcs import Agent
from typing import Dict, Any
import json

def get_user_context():
    # Reuse the same function from intent agent
    pass

def get_driving_directions(query: str) -> Dict[str, Any]:
    # Reuse the same function from navigation agent
    pass

theaters_agent = Agent(
    name="Theaters Agent",
    instructions="""You are a theaters agent that finds and analyzes local theater options.

Your responses must be formatted as JSON matching this schema:
{
    "type": "theaters",
    "title": "Theater Search",
    "description": "Finding showtimes",
    "status": "processing" | "completed" | "error",
    "content": {
        "theaters": [
            {
                "name": string,
                "distance": string,
                "address": string,
                "showTimes": string[],
                "seats": "Multiple seats" | "Limited seats" | "Sold out",
                "formats": string[],
                "amenities": string[],
                "pricing": {
                    "adult": string,
                    "child": string,
                    "senior": string
                }
            }
        ],
        "recommendations": {
            "best_theater": string,
            "best_showtime": string,
            "reasoning": string[]
        },
        "next_agents": ["navigation"],
        "context_used": {
            "location": string,
            "transportation": string,
            "time_preferences": string
        }
    }
}

Consider factors like:
- Distance from user's location
- Available showtimes
- Seat availability
- Theater amenities
- User's transportation method

Always include navigation agent for directions to recommended theater.
Ensure your response is valid JSON matching this schema exactly.""",
    functions=[get_user_context, get_driving_directions],
    model="gpt-4o"
)