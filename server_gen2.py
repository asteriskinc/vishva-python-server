from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
from datetime import datetime
import os
from typing import Dict
from orcs import Orcs, Agent

# Import your agents and functions here
# from agents import IntentAgent, MovieAgent, DirectionsAgent
from test_agents import intent_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration remains the same
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vishva-app-digitalocean-6te3v.ondigitalocean.app")
ALLOWED_ORIGINS = [FRONTEND_URL]

if ENVIRONMENT == "development":
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:8000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self._active_connections: Dict[str, WebSocket] = {}
        self._connection_status: Dict[str, bool] = {}
        self.orcs = Orcs()  # Initialize Orcs instance

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        connection_id = str(id(websocket))
        self._active_connections[connection_id] = websocket
        self._connection_status[connection_id] = True
        logger.info(f"Client connected. Connection ID: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str):
        if connection_id in self._active_connections:
            self._connection_status[connection_id] = False
            del self._active_connections[connection_id]
            del self._connection_status[connection_id]
            logger.info(f"Client disconnected. Connection ID: {connection_id}")

    async def is_connected(self, connection_id: str) -> bool:
        return connection_id in self._connection_status and self._connection_status[connection_id]

    async def send_message(self, connection_id: str, message: dict) -> bool:
        if not await self.is_connected(connection_id):
            logger.warning(f"Attempted to send message to disconnected client: {connection_id}")
            return False

        try:
            websocket = self._active_connections.get(connection_id)
            if websocket:
                await websocket.send_text(json.dumps(message))
                return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await self.disconnect(connection_id)
        return False

    async def process_search_query(self, connection_id: str, query: str):
        """Process search query using the Orcs system"""
        try:
            # Initialize your first agent
            messages = [{"role": "user", "content": query}]
            
            # Run the agent system and stream events
            for event in self.orcs.run(
                agent=initial_agent,
                messages=messages,
                context_variables={"query": query},
                debug=True
            ):
                # Send each agent event to the frontend
                await self.send_message(connection_id, event.to_dict())
                
        except Exception as e:
            logger.error(f"Error processing search: {e}")
            await self.send_message(connection_id, {
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": datetime.now().isoformat()
            })

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = None
    try:
        connection_id = await manager.connect(websocket)
        
        while await manager.is_connected(connection_id):
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("action") == "start_search":
                    await manager.process_search_query(connection_id, message.get("query"))
                else:
                    await manager.send_message(connection_id, {
                        "type": "error",
                        "data": {"message": "Unknown action"},
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected normally")
                break
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                break
    except Exception as e:
        logger.error(f"Error in websocket endpoint: {e}")
    finally:
        if connection_id:
            await manager.disconnect(connection_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)