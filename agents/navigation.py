# app/agents/navigation.py
from orcs import Agent
from typing import Dict, Any, Optional, Tuple
import urllib.parse
import requests
import os
from utils.context import get_user_context

def get_distance(origin: str, destination: str) -> Optional[Tuple[str, str]]:
    """Get distance and duration between locations using Google Distance Matrix API"""
    try:
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': os.getenv('GOOGLE_MAPS_API_KEY')
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] == 'OK':
            distance = data['rows'][0]['elements'][0]['distance']['text']
            duration = data['rows'][0]['elements'][0]['duration']['text']
            return distance, duration
        return None
    except Exception as e:
        print(f"Error getting distance: {str(e)}")
        return None

def get_driving_directions(query: str) -> Dict[str, Any]:
    """Generate driving directions based on query and context"""
    try:
        # Get user context for location information
        user_context = get_user_context()
        user_location = user_context.get('user_location', '').split(',')[0].strip()
        
        # Parse origin and destination
        parts = query.lower().split('to')
        origin = parts[0].replace('from', '').strip() if len(parts) > 1 else user_location
        destination = parts[-1].strip()
        
        # Get distance and duration
        distance_info = get_distance(origin, destination)
        
        # Create Maps URL
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        maps_url = f"https://www.google.com/maps/dir/{origin_encoded}/{destination_encoded}"
        
        response = {
            "directions_url": maps_url,
            "origin": origin,
            "destination": destination,
            "context_used": {
                "user_location": user_location,
            }
        }
        
        if distance_info:
            distance, duration = distance_info
            response.update({
                "distance": distance,
                "duration": duration
            })
            
        return response
        
    except Exception as e:
        return {"error": f"Failed to generate directions: {str(e)}"}

navigation_agent = Agent(
    name="Navigation Agent",
    instructions="""You are a navigation agent that provides optimal routing and directions.

Your responses must be formatted as JSON matching this schema:
{
    "type": "directions",
    "title": "Navigation",
    "description": "Planning your route",
    "status": "processing" | "completed" | "error",
    "content": {
        "route": {
            "origin": string,
            "destination": string,
            "distance": string,
            "duration": string,
            "maps_url": string
        },
        "options": {
            "transport_mode": "driving" | "transit" | "walking",
            "route_type": "fastest" | "shortest" | "recommended",
            "alternatives": [
                {
                    "mode": string,
                    "duration": string,
                    "description": string
                }
            ]
        },
        "recommendations": {
            "best_option": string,
            "leave_by_time": string,
            "parking_info": string,
            "notes": string[]
        },
        "next_agents": [],
        "context_used": {
            "user_location": string,
            "transportation": string,
            "time_context": string
        }
    }
}

Consider factors like:
- User's preferred transportation method
- Current traffic conditions
- Time of day
- Parking availability at destination

Navigation is typically the final agent in the chain.
Ensure your response is valid JSON matching this schema exactly.""",
    functions=[get_distance, get_driving_directions, get_user_context],
    model="gpt-4o"
)