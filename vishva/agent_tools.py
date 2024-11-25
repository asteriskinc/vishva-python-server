# Definte various tools that can be used by the agents like web search, directions, etc.
import requests
from googlesearch import search
from bs4 import BeautifulSoup
import markdown
from typing import Optional, Tuple, Dict, Any
import re
import urllib.parse
from dotenv import load_dotenv
import os

load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')


# User Context Tools 
def get_user_context():
    return {
        "user_preferences": "User likes to watch movies and TV shows.", 
        "user_past_interactions": "User has watched the movie 'Inception' and liked it.",
        "user_name": "Apekshik Panigrahi",
        "user_age": 23,
        "user_location": "220 Ventura Ave, Palo Alto, CA",
        "user_interests": "Traveling, Photography, Hiking",
        "user_occupation": "AI Engineer",
        "user_transportation": "Uses a Tesla Model 3",
        "user_date": "2024-11-03"
    }


# Web Search Tools 
def perform_web_search(query):
    search_results = []
    try:
        for result in search(query, num_results=5):
            search_results.append(result)
        # print(search_results)
        return {"results": search_results}
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}
    
def retrieve_url_content(url):
    try:
        # Send GET request to the URL
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract main content
        content = soup.get_text()
        
        # Convert to markdown
        md_content = markdown.markdown(content)
        
        # print(md_content)
        return {"content": md_content}
    except Exception as e:
        return {"error": f"Failed to open URL: {str(e)}"}
    

# Directions Tools 
def get_distance_and_duration(origin: str, destination: str) -> Optional[Tuple[str, str]]:
    """
    Get distance and duration between two locations using Google Distance Matrix API.
    
    Args:
        origin (str): Starting location
        destination (str): Ending location
        
    Returns:
        Optional[Tuple[str, str]]: Distance and duration if successful, None if failed
    """
    try:
        # URL encode the addresses
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        url = f'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
            distance = data['rows'][0]['elements'][0]['distance']['text']
            duration = data['rows'][0]['elements'][0]['duration']['text']
            return distance, duration
        else:
            print(f"Error: {data['status']}")
            return None
    except Exception as e:
        print(f"Error getting distance: {str(e)}")
        return None


def get_driving_directions(query: str) -> Dict[Any, Any]:
    """
    Generates driving directions based on the user's query and context, including distance and duration.
    
    Args:
        query (str): The user's direction request (e.g., "from Los Angeles to San Francisco")
        
    Returns:
        dict: Contains directions information or error message
    """
    try:
        # Get user context for location information
        user_context = get_user_context()
        user_location = user_context.get('user_location', '').split(',')[0].strip()
        
        # Clean and parse the query
        query = query.lower()
        query = re.sub(r'\s+', ' ', query)  # Normalize whitespace
        
        # Handle different query formats
        if 'to' in query:
            parts = [p.strip() for p in query.split('to') if p.strip()]
            parts = [p.replace('from', '').replace('directions', '').strip() for p in parts]
        else:
            parts = query.replace('from', '').replace('directions', '').strip().split()
            
        # Handle cases where origin isn't specified (use user's location)
        if len(parts) == 1:
            origin = user_location
            destination = parts[0]
        elif len(parts) >= 2:
            origin = parts[0]
            destination = parts[-1]
        else:
            return {"error": "Please specify at least a destination"}
            
        # Clean up origin/destination
        origin = origin.strip()
        destination = destination.strip()
        
        # If origin is "home" or "my place", use user's location
        if origin.lower() in ['home', 'my place', 'my location', 'here']:
            origin = user_location
            
        # Get distance and duration
        distance_and_duration_info = get_distance_and_duration(origin, destination)
        
        # Encode locations for URL
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        # Create Google Maps URL
        maps_url = f"https://www.google.com/maps/dir/{origin_encoded}/{destination_encoded}"
        
        # Add transportation mode based on user context
        transport = user_context.get('user_transportation', '')
        if 'tesla' in transport.lower():
            maps_url += "/data=!4m2!4m1!3e0"  # Driving mode
            transport_msg = "by car"
        elif 'bike' in transport.lower():
            maps_url += "/data=!4m2!4m1!3e1"  # Bicycle mode
            transport_msg = "by bicycle"
        elif 'walking' in transport.lower():
            maps_url += "/data=!4m2!4m1!3e2"  # Walking mode
            transport_msg = "on foot"
        else:
            maps_url += "/data=!4m2!4m1!3e0"  # Default to driving mode
            transport_msg = "by car"
        
        # Create response with distance information if available
        response = {
            "directions_url": maps_url,
            "origin": origin,
            "destination": destination,
            "transport_mode": transport_msg,
            "context_used": {
                "user_location": user_location,
                "transportation": transport
            }
        }
        
        if distance_and_duration_info:
            distance, duration = distance_and_duration_info
            response.update({
                "distance": distance,
                "duration": duration,
                "message": f"Here are the directions from {origin} to {destination} {transport_msg}.\nDistance: {distance}\nEstimated time: {duration}"
            })
        else:
            response.update({
                "message": f"Here are the directions from {origin} to {destination} {transport_msg}."
            })
            
        return response
        
    except Exception as e:
        return {"error": f"Failed to generate directions: {str(e)}"}