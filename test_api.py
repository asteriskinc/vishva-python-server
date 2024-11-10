# test_api.py
import requests
import time
import json

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_search_api():
    # Test data
    search_request = {
        "query": "Where can I watch smile 2?",
        "user_context": {
            "location": "San Francisco",
            "preferences": {
                "genres": ["action", "comedy"]
            }
        }
    }

    # Create search task
    print("Creating search task...")
    response = requests.post(f"{BASE_URL}/api/search", json=search_request)
    if response.status_code != 200:
        print(f"Error creating search: {response.text}")
        return
    
    task_id = response.json()["task_id"]
    print(f"Task ID: {task_id}")

    # Poll for results
    max_attempts = 10
    attempt = 0
    while attempt < max_attempts:
        print(f"\nChecking task status (attempt {attempt + 1})...")
        response = requests.get(f"{BASE_URL}/api/search/{task_id}")
        
        if response.status_code != 200:
            print(f"Error checking status: {response.text}")
            break
            
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if result["status"] == "completed":
            print("\nTask completed successfully!")
            break
        elif result["status"] == "error":
            print("\nTask failed:", result.get("error"))
            break
            
        attempt += 1
        time.sleep(2)  # Wait 2 seconds before next check

if __name__ == "__main__":
    test_search_api()