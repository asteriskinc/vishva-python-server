# orcs/tools/web_tools.py
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel
import aiohttp
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
import json
from googlesearch import search
from ..tool_manager import tool_registry

# Response Models
class SearchResult(BaseModel):
    """Model for a single search result with content"""
    title: str
    url: str
    snippet: str
    source: str
    content: Optional[str] = None
    relevance_score: float = 1.0

class WebSearchResponse(BaseModel):
    """Model for web search results with content"""
    results: List[SearchResult]
    query: str
    total_results: int

class DistanceResult(BaseModel):
    """Model for distance calculation results"""
    origin: str
    destination: str
    distance: Optional[str] = None
    duration: Optional[str] = None
    status: str
    error: Optional[str] = None

class NavigationStep(BaseModel):
    """Model for a single navigation step"""
    instruction: str
    distance: float
    duration: float
    mode: str

class NavigationResponse(BaseModel):
    """Model for navigation directions"""
    steps: List[NavigationStep]
    total_distance: float
    total_duration: float
    start_location: str
    end_location: str
    transport_mode: str

# Combined Web Search and Content Tool
@tool_registry.register(description="Perform a web search and retrieve content from results")
async def web_search(
    query: str,
    num_results: int = 5,
    fetch_content: bool = True
) -> WebSearchResponse:
    """
    Perform a web search and optionally fetch content from result URLs.
    
    Args:
        query: Search query string
        num_results: Number of results to return
        fetch_content: Whether to fetch and parse content from result URLs
    
    Returns:
        WebSearchResponse containing search results and content
    """
    try:
        # Use run_in_executor to run sync Google search in async context
        loop = asyncio.get_running_loop()
        search_results = await loop.run_in_executor(
            None, 
            lambda: list(search(query, num_results=num_results))
        )
        
        # Process search results and fetch content if requested
        processed_results = []
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(search_results):
                source = url.split('/')[2] if '//' in url else url.split('/')[0]
                
                result = SearchResult(
                    title=f"Result from {source}",
                    url=url,
                    snippet=f"Result {i+1} for query: {query}",
                    source=source,
                    relevance_score=1.0 - (i * 0.1)
                )
                
                # Fetch content if requested
                if fetch_content:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Update title if available
                                if soup.title:
                                    result.title = soup.title.string
                                
                                # Extract main content
                                main_content = []
                                for p in soup.find_all('p'):
                                    text = p.get_text().strip()
                                    if text:
                                        main_content.append(text)
                                
                                result.content = "\n".join(main_content)
                                
                                # Update snippet with first paragraph if available
                                if main_content:
                                    result.snippet = main_content[0][:200] + "..."
                    except Exception as e:
                        print(f"Error fetching content from {url}: {str(e)}")
                
                processed_results.append(result)
        
        return WebSearchResponse(
            results=processed_results,
            query=query,
            total_results=len(processed_results)
        )
        
    except Exception as e:
        raise ValueError(f"Search failed: {str(e)}")

# Distance Matrix Tool
@tool_registry.register(description="Calculate distance and duration between locations")
async def get_distance_matrix(
    origin: str,
    destination: str,
    api_key: Optional[str] = None
) -> DistanceResult:
    """
    Calculate distance and duration between two locations using Google Distance Matrix API.
    
    Args:
        origin: Starting location
        destination: Ending location
        api_key: Google Maps API key (optional, will use environment variable if not provided)
    
    Returns:
        DistanceResult containing distance and duration information
    """
    try:
        # Get API key from environment if not provided
        api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise ValueError("Google Maps API key not provided")
        
        # URL encode the addresses
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        # Prepare API request
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': api_key
        }
        
        # Make async request
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
                    element = data['rows'][0]['elements'][0]
                    return DistanceResult(
                        origin=origin,
                        destination=destination,
                        distance=element['distance']['text'],
                        duration=element['duration']['text'],
                        status='OK'
                    )
                else:
                    return DistanceResult(
                        origin=origin,
                        destination=destination,
                        status='ERROR',
                        error=f"API Error: {data['status']}"
                    )
                    
    except Exception as e:
        return DistanceResult(
            origin=origin,
            destination=destination,
            status='ERROR',
            error=str(e)
        )

# Navigation Tool (uses distance matrix)
@tool_registry.register(description="Get navigation directions between locations")
async def get_directions(
    start_location: str,
    end_location: str,
    transport_mode: str = "driving",
    api_key: Optional[str] = None
) -> NavigationResponse:
    """
    Generate navigation directions between two locations.
    
    Args:
        start_location: Starting location
        end_location: Destination location
        transport_mode: Mode of transport (driving, walking, cycling)
        api_key: Google Maps API key (optional)
    
    Returns:
        NavigationResponse containing route information
    """
    # Get distance information first
    distance_result = await get_distance_matrix(start_location, end_location, api_key)
    
    if distance_result.status == 'OK':
        # Convert distance and duration to float values for calculations
        try:
            distance_value = float(distance_result.distance.split()[0])
            duration_value = float(distance_result.duration.split()[0])
        except (ValueError, AttributeError):
            distance_value = 0.0
            duration_value = 0.0
            
        # Create navigation steps (simplified for now)
        steps = [
            NavigationStep(
                instruction=f"Navigate from {start_location} to {end_location}",
                distance=distance_value,
                duration=duration_value,
                mode=transport_mode
            )
        ]
        
        return NavigationResponse(
            steps=steps,
            total_distance=distance_value,
            total_duration=duration_value,
            start_location=start_location,
            end_location=end_location,
            transport_mode=transport_mode
        )
    else:
        raise ValueError(f"Failed to get directions: {distance_result.error}")