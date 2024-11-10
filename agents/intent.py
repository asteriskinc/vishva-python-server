# app/agents/intent.py
from orcs import Agent
from typing import List, Dict, Any
import json

def get_user_context():
    return {
        "user_preferences": "User likes to watch movies and TV shows.", 
        "user_past_interactions": "User has watched the movie 'Inception' and liked it.",
        "user_name": "Apekshik Panigrahi",
        "user_age": 25,
        "user_location": "Deus Ex Machina, Venice, CA",
        "user_interests": "Traveling, Photography, Hiking",
        "user_occupation": "Software Engineer",
        "user_transportation": "Uses a Tesla Model 3",
        "user_date": "2024-11-03"
    }

def transfer_to_movie_agent(query: str) -> Dict[str, Any]:
    return {"next_agent": "movie", "query": query}

def transfer_to_navigation_agent(query: str) -> Dict[str, Any]:
    return {"next_agent": "navigation", "query": query}

intent_agent = Agent(
    name="Intent Agent",
    instructions="""You are an intent agent that analyzes user queries to understand their needs and orchestrate the appropriate responses.

First, examine the user's context to better understand their preferences and situation.

Then, analyze their query to:
1. Break down the request into specific tasks
2. Identify which specialized agents should handle each task
3. Determine the optimal sequence of agent interactions

Your responses must be formatted as JSON matching this schema:
{
    "type": "intent",
    "title": "Intent Analysis",
    "description": "Understanding your request",
    "status": "processing" | "completed" | "error",
    "content": {
        "tasks": [
            "task description 1",
            "task description 2"
        ],
        "identified_intents": [
            {
                "intent_type": "movie_search" | "navigation" | "availability_check" | "theater_search",
                "confidence": number (0-1),
                "relevant_context": string[]
            }
        ],
        "next_agents": ["movie", "navigation", "theaters", "personal"],
        "priority_order": ["agent1", "agent2"],  // Suggested processing order
        "context_used": {
            "location": string,
            "preferences": string[],
            "time_sensitive": boolean
        }
    }
}

Examples of task breakdown:
1. For "Find tickets for Oppenheimer":
   - Check movie availability and format
   - Search local theaters and showtimes
   - Calculate travel time to theaters
   - Consider user's transportation preferences

2. For "What's playing at AMC tonight":
   - Get current showtimes at AMC
   - Check theater location relative to user
   - Consider user's movie preferences
   - Calculate travel options

Always use the provided user context to enhance your analysis.
Ensure your response is valid JSON matching this schema exactly.""",
    functions=[
        get_user_context,
        transfer_to_movie_agent,
        transfer_to_navigation_agent
    ],
    model="gpt-4-0125-preview"
)