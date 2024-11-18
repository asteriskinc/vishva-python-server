import asyncio
import websockets
import json

async def connect_and_send():
    # Replace with your WebSocket server URL
    uri = "ws://localhost:8000/ws"  # Default WebSocket port is 8765
    
    try:
        async with websockets.connect(uri) as websocket:
            # Message to send
            message = {
                "action": "start_search",
                "query": "where do I watch smile 2? after the intent agent call the triage agent"
            }
            
            # Convert message to JSON string and send
            await websocket.send(json.dumps(message))
            print(f"Sent message: {message}")
            
            # Wait for response
            print("\nListening for responses... (Press Ctrl+C to exit)")
            
            # Keep listening for messages until interrupted
            while True:
                try:
                    message = await websocket.recv()
                    try:
                        # Try to parse as JSON and print nicely
                        parsed_message = json.loads(message)
                        print(f"\nReceived: {json.dumps(parsed_message, indent=2)}")
                    except json.JSONDecodeError:
                        # If not JSON, print as is
                        print(f"\nReceived: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed by server")
                    break
            
    except websockets.exceptions.ConnectionRefused:
        print("Connection refused. Make sure the WebSocket server is running.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Run the async function
if __name__ == "__main__":
    asyncio.run(connect_and_send())