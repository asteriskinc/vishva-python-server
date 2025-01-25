from typing import Dict, Any, List
from .orcs_types import Tool
import requests
import urllib.parse
import os
from bs4 import BeautifulSoup
from googlesearch import search

# Web Search Tools
def perform_web_search(query: str) -> Dict[str, Any]:
    """Perform a web search and return results"""
    search_results = []
    try:
        for result in search(query, num_results=5):
            search_results.append(result)
        return {"results": search_results}
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def retrieve_url_content(url: str) -> Dict[str, Any]:
    """Retrieve and parse content from a URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text()
        return {"content": content}
    except Exception as e:
        return {"error": f"Failed to open URL: {str(e)}"}

# Location and Navigation Tools
def get_distance(origin: str, destination: str) -> Dict[str, Any]:
    """Get distance and duration between locations"""
    try:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            return {"error": "Google Maps API key not found"}
            
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': api_key
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
            distance = data['rows'][0]['elements'][0]['distance']['text']
            duration = data['rows'][0]['elements'][0]['duration']['text']
            return {
                "distance": distance,
                "duration": duration,
                "status": "success"
            }
        else:
            return {"error": f"API Error: {data['status']}"}
    except Exception as e:
        return {"error": f"Error getting distance: {str(e)}"}

def get_driving_directions(origin: str, destination: str, transport_mode: str = "driving") -> Dict[str, Any]:
    """Generate driving directions between locations"""
    try:
        # Get distance info first
        distance_info = get_distance(origin, destination)
        if "error" in distance_info:
            return distance_info
            
        # Encode locations for URL
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        # Create Google Maps URL with transport mode
        mode_param = {
            "driving": "!3e0",
            "bicycling": "!3e1",
            "walking": "!3e2",
            "transit": "!3e3"
        }.get(transport_mode.lower(), "!3e0")
        
        maps_url = f"https://www.google.com/maps/dir/{origin_encoded}/{destination_encoded}/data=!4m2!4m1{mode_param}"
        
        return {
            "directions_url": maps_url,
            "origin": origin,
            "destination": destination,
            "transport_mode": transport_mode,
            "distance": distance_info.get("distance"),
            "duration": distance_info.get("duration"),
            "status": "success"
        }
    except Exception as e:
        return {"error": f"Failed to generate directions: {str(e)}"}

# Define the tools
AVAILABLE_TOOLS = [
    Tool(
        name="web_search",
        description="Perform a web search and return results",
        function=perform_web_search,
        parameters={"query": "string"},
        required_params=["query"]
    ),
    Tool(
        name="url_content",
        description="Retrieve and parse content from a URL",
        function=retrieve_url_content,
        parameters={"url": "string"},
        required_params=["url"]
    ),
    Tool(
        name="get_distance",
        description="Get distance and duration between two locations",
        function=get_distance,
        parameters={
            "origin": "string",
            "destination": "string"
        },
        required_params=["origin", "destination"]
    ),
    Tool(
        name="get_directions",
        description="Generate driving directions between locations",
        function=get_driving_directions,
        parameters={
            "origin": "string",
            "destination": "string",
            "transport_mode": "string"
        },
        required_params=["origin", "destination", "transport_mode"]
    )
] 