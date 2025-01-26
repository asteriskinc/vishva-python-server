import asyncio
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from orcs.tools.web_tools import web_search, get_distance_matrix, get_directions

# Load environment variables
load_dotenv()

async def test_web_search():
    """Test the web search functionality"""
    print("\n=== Testing Web Search ===")
    try:
        # Test basic search
        print("\nTesting search with content fetching...")
        results = await web_search(
            query="Best IMAX theaters in New York",
            num_results=3,
            fetch_content=True
        )
        print(f"\nSearch Results for: {results.query}")
        print(f"Total results available: {results.total_results}")
        print(f"Results fetched: {len(results.results)}")
        
        # Print details of each result
        for i, result in enumerate(results.results, 1):
            print(f"\nResult {i}:")
            print(f"Title: {result.title}")
            print(f"URL: {result.url}")
            print(f"Source: {result.source}")
            print(f"Snippet: {result.snippet[:200]}...")
            if result.content:
                print(f"Content length: {len(result.content)} characters")
                print(f"First 200 chars of content: {result.content[:200]}...")
            else:
                print("No content fetched")

        # Test search without content fetching
        print("\nTesting search without content fetching...")
        results_no_content = await web_search(
            query="Popular movies 2024",
            num_results=2,
            fetch_content=False
        )
        print(f"\nSearch Results for: {results_no_content.query}")
        print(f"Total results available: {results_no_content.total_results}")
        print(f"Results fetched: {len(results_no_content.results)}")
        
        # Print details of each result
        for i, result in enumerate(results_no_content.results, 1):
            print(f"\nResult {i}:")
            print(f"Title: {result.title}")
            print(f"URL: {result.url}")
            print(f"Source: {result.source}")
            print(f"Snippet: {result.snippet[:200]}...")
        
    except Exception as e:
        print(f"Error in web search test: {str(e)}")

async def test_distance_matrix():
    """Test the distance matrix functionality"""
    print("\n=== Testing Distance Matrix ===")
    try:
        origins = ["Times Square, New York", "Central Park, New York"]
        destinations = ["Empire State Building, New York"]
        
        for origin in origins:
            for destination in destinations:
                result = await get_distance_matrix(origin, destination)
                print(f"{origin} to {destination}: {result.status}")
                if result.status != 'OK':
                    print(f"Error: {result.error}")
                
    except Exception as e:
        print(f"Error in distance matrix test: {str(e)}")

async def test_directions():
    """Test the navigation directions functionality"""
    print("\n=== Testing Navigation Directions ===")
    try:
        start = "Times Square, New York"
        end = "Empire State Building, New York"
        modes = ["driving", "walking", "cycling"]
        
        for mode in modes:
            result = await get_directions(start, end, transport_mode=mode)
            print(f"{mode.capitalize()}: {result.total_distance}, {result.total_duration}")
                
    except Exception as e:
        print(f"Error in directions test: {str(e)}")

async def main():
    """Run all tests"""
    print("Starting Web Tools Tests...")
    
    # Test web search
    await test_web_search()
    
    # Test distance matrix
    await test_distance_matrix()
    
    # Test directions
    await test_directions()
    
    print("\nTests completed!")

if __name__ == "__main__":
    asyncio.run(main())