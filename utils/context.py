# utils/context.py
from datetime import datetime
from typing import Dict, Any

def get_user_context() -> Dict[str, Any]:
    """
    Get user context information including preferences, location, and other relevant details.
    In a production environment, this would likely fetch from a database or user service.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "user_preferences": {
            "movies": ["Action", "Sci-Fi", "Drama"],
            "formats": ["IMAX", "Dolby"],
            "viewing_times": "Evening preferred"
        },
        "user_past_interactions": [
            {"movie": "Inception", "rating": "liked"},
            {"movie": "Oppenheimer", "rating": "excellent"}
        ],
        "user_info": {
            "name": "Apekshik Panigrahi",
            "age": 25,
            "occupation": "Software Engineer"
        },
        "user_location": {
            "current": "Deus Ex Machina, Venice, CA",
            "coordinates": {"lat": 33.9850, "lng": -118.4695},
            "preferred_radius": "10 miles"
        },
        "user_interests": [
            "Traveling",
            "Photography",
            "Hiking"
        ],
        "transportation": {
            "primary": "Tesla Model 3",
            "preferences": ["driving", "ride-share"],
            "parking_required": True
        },
        "session_context": {
            "date": current_date,
            "time_of_day": datetime.now().strftime("%H:%M"),
            "timezone": "America/Los_Angeles"
        }
    }