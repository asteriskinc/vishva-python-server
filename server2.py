# this was the old server.py code for the websocket simulation for video processing demo. Just for reference.
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
import json
from datetime import datetime
from typing import Set
import os

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
        self._active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.info(f"Client connected. Total connections: {len(self._active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total connections: {len(self._active_connections)}")

    async def send_update(self, websocket: WebSocket, message_type: str, data: dict):
        try:
            message = {
                "type": message_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending update: {e}")
            await self.disconnect(websocket)

manager = ConnectionManager()

async def simulate_video_processing(websocket: WebSocket):
    """Simulates a long-running video processing task with multiple steps"""
    
    # Simulate loading video
    await manager.send_update(websocket, "status", {
        "step": "loading",
        "message": "Loading video file...",
        "progress": 0
    })
    await asyncio.sleep(2)  # Simulate work

    # Simulate analyzing frames
    total_frames = 300
    for frame in range(0, total_frames, 30):
        progress = (frame / total_frames) * 100
        await manager.send_update(websocket, "status", {
            "step": "analyzing",
            "message": f"Analyzing frame {frame}/{total_frames}",
            "progress": progress
        })
        await asyncio.sleep(0.5)  # Simulate work

    # Simulate applying filters
    filters = ["noise_reduction", "color_correction", "stabilization"]
    for idx, filter_name in enumerate(filters):
        progress = ((idx + 1) / len(filters)) * 100
        await manager.send_update(websocket, "status", {
            "step": "filtering",
            "message": f"Applying {filter_name}...",
            "progress": progress
        })
        await asyncio.sleep(1.5)  # Simulate work

    # Simulate export
    await manager.send_update(websocket, "status", {
        "step": "exporting",
        "message": "Exporting processed video...",
        "progress": 100
    })
    await asyncio.sleep(2)  # Simulate work

    # Send completion message
    await manager.send_update(websocket, "complete", {
        "message": "Video processing completed successfully!",
        "stats": {
            "frames_processed": total_frames,
            "filters_applied": len(filters),
            "duration_seconds": 10
        }
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await manager.connect(websocket)
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("action") == "start_processing":
                    await simulate_video_processing(websocket)
                else:
                    await manager.send_update(websocket, "error", {
                        "message": "Unknown action"
                    })
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected normally")
                break
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                break
    except Exception as e:
        logger.error(f"Error handling WebSocket connection: {e}")
    finally:
        await manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Listen on all available interfaces
        port=8000,
        ssl_keyfile=None,  # Add these if you want to use SSL locally
        ssl_certfile=None,
    )