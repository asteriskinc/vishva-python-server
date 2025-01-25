# websocket_manager.py
from typing import Dict, Optional, List, Callable, Awaitable
from fastapi import WebSocket
import asyncio
from datetime import datetime
from collections import deque

class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._message_queues: Dict[str, deque] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """
        Connect a new WebSocket for a task, handling any existing connections gracefully
        """
        # Get or create a lock for this task
        if task_id not in self._locks:
            self._locks[task_id] = asyncio.Lock()
            
        async with self._locks[task_id]:
            # If there's an existing connection, close it gracefully
            if task_id in self._connections:
                try:
                    await self._connections[task_id].close()
                except Exception:
                    pass  # Ignore errors from closing existing connection
                
                # Cancel any active message processing task
                if task_id in self._active_tasks:
                    self._active_tasks[task_id].cancel()
                    try:
                        await self._active_tasks[task_id]
                    except asyncio.CancelledError:
                        pass
            
            # Accept the new connection
            await websocket.accept()
            
            # Store the new connection
            self._connections[task_id] = websocket
            
            # Initialize or clear message queue
            if task_id not in self._message_queues:
                self._message_queues[task_id] = deque()
            
            # Start message processing task
            self._active_tasks[task_id] = asyncio.create_task(
                self._process_message_queue(task_id)
            )
    
    async def disconnect(self, task_id: str) -> None:
        """
        Clean up resources for a task
        """
        async with self._locks[task_id]:
            if task_id in self._active_tasks:
                self._active_tasks[task_id].cancel()
                try:
                    await self._active_tasks[task_id]
                except asyncio.CancelledError:
                    pass
                del self._active_tasks[task_id]
            
            if task_id in self._connections:
                try:
                    await self._connections[task_id].close()
                except Exception:
                    pass
                del self._connections[task_id]
            
            if task_id in self._message_queues:
                del self._message_queues[task_id]
    
    async def send_message(self, task_id: str, message: dict) -> None:
        """
        Queue a message to be sent to the WebSocket
        """
        if task_id in self._message_queues:
            self._message_queues[task_id].append(message)
    
    async def _process_message_queue(self, task_id: str) -> None:
        """
        Process queued messages for a task
        """
        while True:
            try:
                # Wait for messages in the queue
                while self._message_queues[task_id]:
                    message = self._message_queues[task_id].popleft()
                    websocket = self._connections.get(task_id)
                    
                    if websocket:
                        try:
                            await websocket.send_json(message)
                        except Exception as e:
                            print(f"Error sending message for task {task_id}: {str(e)}")
                            # Requeue the message if sending failed
                            self._message_queues[task_id].appendleft(message)
                            break
                
                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing message queue for task {task_id}: {str(e)}")
                await asyncio.sleep(1)  # Longer delay on error
    
    def is_connected(self, task_id: str) -> bool:
        """
        Check if a task has an active connection
        """
        return task_id in self._connections and task_id in self._active_tasks
    
    async def receive_json(self, task_id: str) -> Optional[dict]:
        """
        Receive a JSON message from the WebSocket
        """
        if task_id in self._connections:
            try:
                return await self._connections[task_id].receive_json()
            except Exception as e:
                print(f"Error receiving message for task {task_id}: {str(e)}")
                return None
        return None