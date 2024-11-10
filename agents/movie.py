# app/agents/movie.py
from orcs import Agent
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup

def perform_web_search(query: str) -> Dict[str, Any]:
    """Simulated web search for movie information"""
    # Implementation would use actual search API
    search_results = []
    try:
        # Simulated search results
        return {"results": search_results}
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def retrieve_url_content(url: str) -> Dict[str, Any]:
    """Retrieve and parse content from URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text()
        return {"content": content}
    except Exception as e:
        return {"error": f"Failed to open URL: {str(e)}"}

def transfer_to_theaters_agent(movie_info: Dict[str, Any]) -> Dict[str, Any]:
    return {"next_agent": "theaters", "movie_info": movie_info}

movie_agent = Agent(
    name="Movie Agent",
    instructions="""You are a movie agent that handles movie-related queries and searches.

Your responses must be formatted as JSON matching this schema:
{
    "type": "availability",
    "title": "Movie Search",
    "description": "Finding movie information",
    "status": "processing" | "completed" | "error",
    "content": {
        "movie": {
            "title": string,
            "release_date": string,
            "runtime": string,
            "rating": string,
            "genres": string[]
        },
        "availability": {
            "in_theaters": boolean,
            "streaming": boolean,
            "streaming_platforms": string[],
            "theater_release_date": string?,
            "streaming_release_date": string?
        },
        "recommendations": {
            "theaters_nearby": boolean,
            "best_viewing_format": "standard" | "imax" | "dolby" | "3d",
            "similar_movies": string[]
        },
        "next_agents": ["theaters" | "navigation"],
        "context_used": {
            "user_location": string,
            "preferences": string[]
        }
    }
}

Use the web search function to find accurate movie information.
Check both theatrical and streaming availability.
Consider user context and preferences when making recommendations.
If theaters are found nearby, include both "theaters" and "navigation" in next_agents.

Ensure your response is valid JSON matching this schema exactly.""",
    functions=[
        perform_web_search,
        retrieve_url_content,
        transfer_to_theaters_agent
    ],
    model="gpt-4-0125-preview"
)