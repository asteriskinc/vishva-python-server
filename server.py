from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional, Any
import json
import asyncio
import time
from pydantic import BaseModel
from orcs import Orcs
import logging
from datetime import datetime
import traceback
from enum import Enum

from agents import intent_agent
from agent_schemas import MovieListResponse

# Configure logging
logger = logging.getLogger('orcs_server')
logger.setLevel(logging.INFO)

# Create console handler with a nice formatter
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create a formatter that includes timestamp, level, and module
formatter = logging.Formatter(
    '\033[36m%(asctime)s\033[0m | '  # Cyan timestamp
    '\033[1m%(levelname)8s\033[0m | ' # Bold level
    '\033[35m%(module)s\033[0m | '    # Regular message
    '%(message)s'                      
)
ch.setFormatter(formatter)
logger.addHandler(ch)

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

class ResponseType(Enum):
    THEATERS = "theaters"
    ERROR = "error"
    GENERAL = "general"
    DIRECTIONS = "directions"

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

    def parse_final_response(self, messages: list, agent_name: str) -> tuple[str, Dict[str, Any]]:
        """
        Parse the final response from the agent chain to determine the response type and structure.
        Returns the response type as a string and the parsed data as a dict.
        """
        try:
            final_message = messages[-1]
            logger.info(f"Parsing final response from {agent_name}")
            
            if agent_name == "Movie Agent":
                try:
                    completion = self.orcs_client.client.beta.chat.completions.parse(
                        model="gpt-4o-2024-08-06",
                        messages=[
                            {"role": "system", "content": "Extract the movie theaters and showtime information."},
                            {"role": "user", "content": final_message["content"]}
                        ],
                        response_format=MovieListResponse,
                    )
                    
                    theaters_data = completion.choices[0].message.parsed
                    logger.info(f"Found theaters data: {theaters_data}")
                    return ResponseType.THEATERS.value, {
                        "theaters": [theater.model_dump() for theater in theaters_data.theaters],
                        "count": len(theaters_data.theaters)
                    }
                except Exception as e:
                    logger.warning(f"Failed to parse theater response: {e}")
            
            # Default to general response
            return ResponseType.GENERAL.value, {
                "message": final_message.content if hasattr(final_message, 'content') else str(final_message)
            }
            
        except Exception as e:
            logger.error(f"Error parsing final response: {e}")
            return ResponseType.ERROR.value, {"error": str(e)}

    async def process_agent_conversation(self, current_agent, messages, websocket):
        timestamp = time.time()
        
        logger.info(f"Starting conversation with {current_agent.name}")
        yield {
            "type": "agent_start",
            "agent": current_agent.name,
            "timestamp": timestamp,
            "data": {"message": f"Starting processing with {current_agent.name}"}
        }

        try:
            logger.info("Running agent with stream=True")
            streamed_response = self.orcs_client.run(
                agent=current_agent,
                messages=messages,
                context_variables={},
                stream=True
            )

            current_content = ""
            last_agent = current_agent.name

            logger.info("Starting to process stream")
            for chunk in streamed_response:
                timestamp = time.time()
                logger.debug(f"Received chunk: {chunk}")

                if "sender" in chunk and chunk["sender"] != last_agent:
                    last_agent = chunk["sender"]
                    logger.info(f"Agent switch detected: {current_agent.name} -> {last_agent}")
                    yield {
                        "type": "agent_switch",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"previous_agent": current_agent.name}
                    }

                if "content" in chunk and chunk["content"]:
                    current_content += chunk["content"]
                    logger.debug(f"Content chunk: {chunk['content'][:100]}...")
                    yield {
                        "type": "content",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"content": chunk["content"]}
                    }

                if "tool_calls" in chunk and chunk["tool_calls"]:
                    logger.info(f"Processing tool calls from {last_agent}")
                    for tool_call in chunk["tool_calls"]:
                        if tool_call["function"]["name"]:
                            try:
                                args = json.loads(tool_call["function"]["arguments"])
                            except json.JSONDecodeError:
                                args = tool_call["function"]["arguments"]
                                
                            logger.info(f"Tool call: {tool_call['function']['name']} with args: {args}")
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
                    logger.info(f"End delimiter received, final content length: {len(current_content)}")
                    yield {
                        "type": "agent_complete",
                        "agent": last_agent,
                        "timestamp": timestamp,
                        "data": {"final_content": current_content}
                    }
                    current_content = ""

                if "response" in chunk:
                    response = chunk["response"]
                    logger.info(f"Received response object with agent: {response.agent.name if response.agent else 'None'}")
                    
                    if response.agent and response.agent.name != current_agent.name:
                        logger.info(f"Switching to new agent: {response.agent.name}")
                        async for event in self.process_agent_conversation(
                            response.agent,
                            messages,
                            websocket
                        ):
                            yield event
                    else:
                        logger.info("Conversation complete, parsing final response")
                        response_type, parsed_response = self.parse_final_response(
                            response.messages, 
                            current_agent.name
                        )

                        yield {
                            "type": "content",
                            "agent": "Parser",
                            "timestamp": timestamp,
                            "data": {"content": parsed_response}
                        }
                        
                        # Yield response with parsed data in message
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
            logger.error(f"Error in process_agent_conversation: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
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