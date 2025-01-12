# test_dict_format.py
from pydantic import BaseModel
from typing import List
from orcs_types import Agent
import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

# Define our dictionary format
class DictList(BaseModel):
    class Item(BaseModel):
        key: str
        value: str
    items: List[Item]
    
    def to_dict(self):
        return {item.key: item.value for item in self.items}

# Simple test schema
class TestRestaurant(BaseModel):
    name: str
    properties: DictList  # Test our dictionary format

class TestResponse(BaseModel):
    restaurant: TestRestaurant
    metadata: DictList

# Test agent with very simple instructions
TestAgent = Agent(
    name="Test Agent",
    model="gpt-4o-mini-2024-07-18",
    instructions="""You are a test agent. Respond with a restaurant and its properties.

Example response format:
{
    "restaurant": {
        "name": "Test Restaurant",
        "properties": {
            "items": [
                {"key": "cuisine", "value": "Italian"},
                {"key": "price", "value": "moderate"}
            ]
        }
    },
    "metadata": {
        "items": [
            {"key": "request_time", "value": "evening"},
            {"key": "location", "value": "downtown"}
        ]
    }
}""",
    response_format=TestResponse
)

async def test_dict_format():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found")

    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=api_key)
    
    try:
        print("\nMaking API call to test dictionary format...")
        
        # First, let's print the schema we're sending
        print("\nResponse Schema:")
        print(TestResponse.model_json_schema())
        
        completion = await client.beta.chat.completions.parse(
            model=TestAgent.model,
            messages=[
                {
                    "role": "system",
                    "content": TestAgent.instructions
                },
                {
                    "role": "user",
                    "content": "Find an Italian restaurant"
                }
            ],
            response_format=TestAgent.response_format
        )
        
        print("\nAPI call successful!")
        response = completion.choices[0].message.parsed
        
        # Test the dictionary conversion
        print("\nRestaurant Details:")
        print(f"Name: {response.restaurant.name}")
        
        # Convert and display the properties dictionary
        props_dict = response.restaurant.properties.to_dict()
        print("\nProperties as dictionary:")
        for key, value in props_dict.items():
            print(f"{key}: {value}")
            
        # Convert and display the metadata dictionary
        meta_dict = response.metadata.to_dict()
        print("\nMetadata as dictionary:")
        for key, value in meta_dict.items():
            print(f"{key}: {value}")
        
        # Verify the types
        print("\nType Information:")
        print(f"props_dict type: {type(props_dict)}")
        print(f"meta_dict type: {type(meta_dict)}")
        
    except Exception as e:
        print(f"\nError during API call:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_dict_format()) 