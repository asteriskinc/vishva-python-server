# server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
import json
from datetime import datetime
from typing import Set
import os
from orcs import Orcs, Agent  # Import your agent system

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Get environment variables with defaults
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vishva-app-digitalocean-6te3v.ondigitalocean.app")

# Configure CORS based on environment
ALLOWED_ORIGINS = [
    FRONTEND_URL,  # Production frontend
]

# Add localhost for development
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

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        connection_id = str(id(websocket))
        self._active_connections[connection_id] = websocket
        self._connection_status[connection_id] = True
        logger.info(f"Client connected. Connection ID: {connection_id}. Total connections: {len(self._active_connections)}")
        return connection_id

    async def disconnect(self, connection_id: str):
        if connection_id in self._active_connections:
            self._connection_status[connection_id] = False
            del self._active_connections[connection_id]
            del self._connection_status[connection_id]
            logger.info(f"Client disconnected. Connection ID: {connection_id}. Total connections: {len(self._active_connections)}")

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

    async def send_agent_update(self, connection_id: str, agent_name: str, status: str, data: dict = None) -> bool:
        message = {
            "type": "agent_update",
            "data": {
                "agent": {
                    "name": agent_name,
                    "currentTask": data.get("currentTask") if data else None
                },
                "status": status,
                **(data or {})
            },
            "timestamp": datetime.now().isoformat()
        }
        return await self.send_message(connection_id, message)

    async def send_task_complete(self, connection_id: str, task_id: str, message: str = None) -> bool:
        complete_message = {
            "type": "task_complete",
            "data": {
                "taskId": task_id,
                "message": message
            },
            "timestamp": datetime.now().isoformat()
        }
        return await self.send_message(connection_id, complete_message)

manager = ConnectionManager()

async def process_search_query(connection_id: str, query: str):
    """Process search query using the agent system"""
    try:
        # Intent Agent
        if await manager.send_agent_update(connection_id, "Intent Agent", 
            "Analyzing search query...", {"currentTask": "intent"}):
            await asyncio.sleep(4)
            await manager.send_task_complete(connection_id, "intent", "Search query analyzed")

        # Availability Check
        if await manager.send_agent_update(connection_id, "Movie Agent", 
            "Checking movie availability...", {"currentTask": "availability"}):
            await asyncio.sleep(3)
            await manager.send_task_complete(connection_id, "availability", "Movie found in theaters")

        # Find Theaters
        if await manager.send_agent_update(connection_id, "Movie Agent", 
            "Locating nearby theaters...", 
            {
                "currentTask": "theaters",
                "theaters": [
                    {
                        "name": "AMC Universal CityWalk",
                        "distance": "2.5 miles",
                        "nextShowtime": "7:30 PM"
                    },
                    {
                        "name": "Regal LA Live",
                        "distance": "3.8 miles",
                        "nextShowtime": "8:00 PM"
                    }
                ]
            }):
            await asyncio.sleep(3   )
            await manager.send_task_complete(connection_id, "theaters", "Found nearby theaters")

        # Get Directions
        if await manager.send_agent_update(connection_id, "Directions Agent", 
            "Calculating routes to theaters...", {"currentTask": "directions"}):
            await asyncio.sleep(3.5)
            await manager.send_task_complete(connection_id, "directions", "Route planning completed")

    except Exception as e:
        logger.error(f"Error processing search: {e}")
        await manager.send_message(connection_id, {
            "type": "error",
            "data": {"message": str(e)},
            "timestamp": datetime.now().isoformat()
        })

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
                    await process_search_query(connection_id, message.get("query"))
                else:
                    await manager.send_message(connection_id, {
                        "type": "error",
                        "data": {"message": "Unknown action"},
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected normally. Connection ID: {connection_id}")
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