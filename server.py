from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import asyncio
import time
from pydantic import BaseModel
from orcs import Orcs

from agents import intent_agent

class AgentEvent(BaseModel):
    type: str
    agent: str
    data: Optional[dict] = None
    timestamp: float

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Store conversation history per connection
        self.conversation_history: Dict[WebSocket, List[dict]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Initialize empty conversation history for new connection
        self.conversation_history[websocket] = []

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            # Clean up conversation history
            if websocket in self.conversation_history:
                del self.conversation_history[websocket]

    async def broadcast_event(self, event: dict, websocket: WebSocket):
        try:
            if websocket in self.active_connections:
                await websocket.send_json(event)
        except Exception as e:
            print(f"Error broadcasting event: {e}")
            self.disconnect(websocket)

class OrcsWebSocketServer:
    def __init__(self):
        self.app = FastAPI()
        self.manager = WebSocketManager()
        self.orcs_client = Orcs()
        self.setup_routes()

    def setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.manager.connect(websocket)
            try:
                await self.handle_websocket(websocket)
            except WebSocketDisconnect:
                print("Client disconnected")
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                self.manager.disconnect(websocket)

    async def handle_websocket(self, websocket: WebSocket):
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("action") == "start_search":
                    query = data.get("query")
                    if not query:
                        await self.manager.broadcast_event({
                            "type": "error",
                            "data": {"message": "No query provided"},
                            "timestamp": time.time()
                        }, websocket)
                        continue

                    # Get existing conversation history or start new one
                    history = self.manager.conversation_history.get(websocket, [])
                    
                    # Add user's new query to history
                    history.append({"role": "user", "content": query})
                    
                    # Process the conversation with streaming
                    async for event in self.process_agent_conversation(intent_agent, history, websocket):
                        await self.manager.broadcast_event(event, websocket)
                        
                        # If this is a completion event, save the assistant's response
                        if event['type'] == 'agent_complete':
                            history.append({
                                "role": "assistant", 
                                "content": event['data']['final_content']
                            })
                    
                    # Update the conversation history
                    self.manager.conversation_history[websocket] = history
                
                elif data.get("action") == "clear_history":
                    # Add ability to clear conversation history
                    self.manager.conversation_history[websocket] = []
                    await self.manager.broadcast_event({
                        "type": "info",
                        "data": {"message": "Conversation history cleared"},
                        "timestamp": time.time()
                    }, websocket)
                
                elif data.get("action") == "close":
                    break

        except WebSocketDisconnect:
            raise
        except Exception as e:
            await self.manager.broadcast_event({
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": time.time()
            }, websocket)

    async def process_agent_conversation(self, current_agent, messages, websocket):
        timestamp = time.time()
        
        yield {
            "type": "agent_start",
            "agent": current_agent.name,
            "timestamp": timestamp,
            "data": {"message": f"Starting processing with {current_agent.name}"}
        }

        try:
            structured_response = True
            response = self.orcs_client.run(
                agent=current_agent,
                messages=messages,  # Now using full conversation history
                context_variables={},
                stream=not structured_response
            )

            if structured_response:
                response = [response.messages[-1]]

            current_content = ""
            last_agent = current_agent.name

            for chunk in response:
                timestamp = time.time()

                if "sender" in chunk and chunk["sender"] != last_agent:
                    last_agent = chunk["sender"]
                    yield {
                        "type": "agent_switch",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"previous_agent": current_agent.name}
                    }

                if "content" in chunk and chunk["content"]:
                    current_content += chunk["content"]
                    yield {
                        "type": "content",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"content": chunk["content"]}
                    }

                if "tool_calls" in chunk and chunk["tool_calls"]:
                    for tool_call in chunk["tool_calls"]:
                        if tool_call["function"]["name"]:
                            try:
                                args = json.loads(tool_call["function"]["arguments"])
                            except json.JSONDecodeError:
                                args = tool_call["function"]["arguments"]
                                
                            yield {
                                "type": "tool_call",
                                "agent": last_agent,
                                "timestamp": timestamp,
                                "data": {
                                    "tool": tool_call["function"]["name"],
                                    "arguments": args
                                }
                            }

                if "delim" in chunk and chunk["delim"] == "end" and current_content:
                    yield {
                        "type": "agent_complete",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"final_content": current_content}
                    }
                    current_content = ""

                if "response" in chunk:
                    response = chunk["response"]
                    if response.agent and response.agent.name != current_agent.name:
                        # Process the new agent's conversation with full history
                        async for event in self.process_agent_conversation(
                            response.agent,
                            messages,  # Pass full history to new agent
                            websocket
                        ):
                            yield event
                    else:
                        yield {
                            "type": "conversation_complete",
                            "agent": last_agent,
                            "timestamp": timestamp,
                            "data": {
                                "messages": response.messages,
                                "final_agent": response.agent.name if response.agent else None
                            }
                        }

        except Exception as e:
            yield {
                "type": "error",
                "agent": current_agent.name,
                "timestamp": time.time(),
                "data": {"message": f"Error in agent processing: {str(e)}"}
            }

def create_app():
    server = OrcsWebSocketServer()
    return server.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)