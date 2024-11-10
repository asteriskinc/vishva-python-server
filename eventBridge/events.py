# events.py
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

class EventType(Enum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    FUNCTION_CALL_START = "function_call_start"
    FUNCTION_CALL_END = "function_call_end"
    AGENT_OUTPUT = "agent_output"
    AGENT_HANDOFF = "agent_handoff"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"

@dataclass
class Event:
    type: EventType
    agent_name: str
    timestamp: str = None
    data: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.data:
            self.data = {}

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": {
                "agent": {
                    "name": self.agent_name,
                    "currentTask": self.data.get("currentTask")
                },
                **self.data
            },
            "timestamp": self.timestamp
        }