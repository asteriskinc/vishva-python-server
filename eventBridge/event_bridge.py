# event_bridge.py
from events import Event, EventType
class EventBridge:
    def __init__(self, websocket_manager):
        self.manager = websocket_manager
        
    async def emit(self, connection_id: str, event: Event) -> bool:
        """Emit an event to the frontend through WebSocket"""
        return await self.manager.send_message(connection_id, event.to_dict())

    async def handle_orcs_event(self, connection_id: str, delta: dict, active_agent: str):
        """Transform Orcs events into frontend events"""
        if "delim" in delta:
            if delta["delim"] == "start":
                event = Event(
                    type=EventType.AGENT_START,
                    agent_name=active_agent,
                    data={"currentTask": "Processing request..."}
                )
                await self.emit(connection_id, event)
            
            elif delta["delim"] == "end":
                event = Event(
                    type=EventType.AGENT_END,
                    agent_name=active_agent,
                    data={"currentTask": "Completed"}
                )
                await self.emit(connection_id, event)
                
        elif "tool_calls" in delta:
            event = Event(
                type=EventType.FUNCTION_CALL_START,
                agent_name=active_agent,
                data={
                    "currentTask": f"Calling function: {delta['tool_calls'][0]['function']['name']}",
                    "function": delta['tool_calls'][0]['function']
                }
            )
            await self.emit(connection_id, event)
            
        elif "content" in delta and delta["content"]:
            event = Event(
                type=EventType.AGENT_OUTPUT,
                agent_name=active_agent,
                data={
                    "currentTask": "Generating response",
                    "content": delta["content"]
                }
            )
            await self.emit(connection_id, event)