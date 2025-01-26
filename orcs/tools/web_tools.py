# orcs/tools/web_tools.py
import os
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel
import aiohttp
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
import json
from googlesearch import search
from ..tool_manager import tool_registry
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

@tool_registry.register(description="Perform a web search using Brave Search API")
async def web_search(
    query: str,
    num_results: int = 5,
    fetch_content: bool = True
) -> WebSearchResponse:
    """
    Perform a web search using Brave Search API and optionally fetch content from results.
    
    Args:
        query: Search query string
        num_results: Number of results to return (max 20)
        fetch_content: Whether to fetch and parse content from result URLs
    """
    try:
        logger.info(f"Performing web search: {query}")

        # Get API key from environment
        api_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY not found in environment variables")

        # Prepare the search request
        brave_search_url = 'https://api.search.brave.com/res/v1/web/search'
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': api_key
        }
        params = {
            'q': query,
            'count': min(num_results, 20),  # Brave limits to 20 results per request
            'search_lang': 'en',
            'safesearch': 'moderate',
            'extra_snippets': 'true',  # Get more detailed snippets
            'format': 'json'
        }

        total_results = 0
        # Perform the search
        async with aiohttp.ClientSession() as session:
            async with session.get(brave_search_url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Brave Search API error: {error_text}")
                    raise ValueError(f"Brave Search API returned status {response.status}")
                
                search_data = await response.json()
                total_results = search_data.get('web', {}).get('total_results', 0)

        # Process search results
        processed_results = []
        if 'web' in search_data and 'results' in search_data['web']:
            async with aiohttp.ClientSession() as session:
                for i, result in enumerate(search_data['web']['results']):                    
                    # Create search result object
                    search_result = SearchResult(
                        title=result['title'],
                        url=result['url'],
                        snippet=result.get('description', ''),
                        source=urllib.parse.urlparse(result['url']).netloc,
                        relevance_score=1.0 - (i * 0.1)
                    )

                    # Fetch content if requested
                    if fetch_content:
                        try:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            async with session.get(result['url'], headers=headers, timeout=10) as response:
                                if response.status == 200:
                                    html = await response.text()
                                    
                                    soup = BeautifulSoup(html, 'html.parser')
                                    
                                    # Extract main content
                                    main_content = []
                                    for p in soup.find_all('p'):
                                        text = p.get_text().strip()
                                        if text:
                                            main_content.append(text)
                                    
                                    search_result.content = "\n".join(main_content)
                                    logger.info(f"Successfully fetched content from {result['url']}")
                        except Exception as e:
                            logger.error(f"Error fetching content from {result['url']}: {str(e)}")
                    
                    processed_results.append(search_result)

        logger.info(f"Search completed with {len(processed_results)} results")
        
        return WebSearchResponse(
            results=processed_results,
            query=query,
            total_results=total_results
        )

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
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