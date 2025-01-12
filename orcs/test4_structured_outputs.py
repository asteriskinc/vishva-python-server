# test_response_format.py
from pydantic import BaseModel
from typing import List, Dict  # Note: Using typing module's List and Dict
from orcs_types import Agent
import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

# Simplified response format for testing
class SimpleRecommendation(BaseModel):
    title: str
    description: str 
    rating: float

class SimpleConciergeResponse(BaseModel):
    recommendations: List[SimpleRecommendation]  # Changed to capital List
    search_criteria: dict[str, str]              # Changed to capital Dict
    total_options: int

# Define a simple test agent
TestAgent = Agent(
    name="Test Concierge",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a simple recommendation agent. Your task is to:
1. Provide basic restaurant recommendations
2. Include title and ratings
3. Keep descriptions brief""",
    response_format=SimpleConciergeResponse
)

async def test_agent_response():
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found")

    client = AsyncOpenAI(api_key=api_key)
    
    input_data = {
        "request": "Find a nice restaurant",
        "preferences": {
            "cuisine": "Italian",
            "price_range": "moderate"
        }
    }

    try:
        print("Making API call to test response format...")
        completion = await client.beta.chat.completions.parse(
            model=TestAgent.model,
            messages=[
                {
                    "role": "system",
                    "content": TestAgent.instructions
                },
                {
                    "role": "user",
                    "content": str(input_data)
                }
            ],
            response_format=TestAgent.response_format
        )
        
        print("\nAPI call successful!")
        print("Parsed response:", completion.choices[0].message.parsed)
        
    except Exception as e:
        print(f"\nError during API call:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agent_response())