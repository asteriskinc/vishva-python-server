# orcs/orcs_types.py
import json, inspect
from typing import Callable, Dict, Optional, List, Any, Union, Type
from pydantic import BaseModel, Field, model_serializer
from enum import Enum

"""------------Dict Format for OpenAI Compatibility------------"""
class DictList(BaseModel):
    class Item(BaseModel):
        key: str
        value: str
    items: List[Item]
    
    def to_dict(self):
        return {item.key: item.value for item in self.items}

"""------------Our Core Classes and Types Here------------"""

AgentTool = Callable[[], str]

class Tool(BaseModel):
    """Represents a tool that can be used by agents"""
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any]
    required_params: List[str]

    def get_schema(self) -> Dict[str, Any]:
        """Get the OpenAI function schema for this tool"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }

        signature = inspect.signature(self.function)
        parameters = {}
        for param in signature.parameters.values():
            if param.name == 'self' or param.name.startswith('_'):
                continue
            param_type = type_map.get(param.annotation, "string")
            parameters[param.name] = {"type": param_type}

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": self.required_params,
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    class Config:
        arbitrary_types_allowed = True

class Agent(BaseModel):
    """Represents an agent that can execute tasks"""
    name: str
    model: str
    instructions: str
    response_format: Type[BaseModel]
    tools: List[Tool] = Field(default_factory=list)  # Add tools to agents
    tool_choice: Optional[str] | None = None
    parallel_tool_calls: bool = True

    @model_serializer
    def serialize_model(self) -> dict:
        """Custom serialization for Agent class"""
        return {
            "name": self.name,
            "model": self.model,
            "instructions": self.instructions if isinstance(self.instructions, str) else self.instructions(),
            "tool_choice": self.tool_choice,
            "parallel_tool_calls": self.parallel_tool_calls,
            # Convert response_format to string representation if it's a class
            "response_format": (
                self.response_format.__name__ 
                if isinstance(self.response_format, type) 
                else str(self.response_format)
            )
        }

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskResult(BaseModel):
    """Result of a task execution"""
    status: TaskStatus
    data: dict
    message: str
    timestamp: str

class TaskDependency(BaseModel):
    """Defines a dependency between tasks"""
    task_id: str
    subtask_id: str

class SubTask(BaseModel):
    """Represents a subtask"""
    subtask_id: str
    task_id: str
    agent: Agent
    dependencies: List[TaskDependency] = Field(default_factory=list)
    title: str
    detail: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    # Frontend-specific fields
    icon: Optional[str] = None
    category: int = 1  # 1: Direct task, 2: Optional task
    approved: Optional[bool] = None
    userContext: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def can_execute(self, completed_tasks: Dict[str, TaskResult]) -> bool:
        """Check if this subtask can be executed based on its dependencies"""
        if not self.dependencies:
            return True
        return all(
            dep.task_id in completed_tasks and
            completed_tasks[dep.task_id].status == TaskStatus.COMPLETED
            for dep in self.dependencies
        )

class Task(BaseModel): 
    """Represents a task"""
    task_id: str
    query: str = ""
    subtasks: List[SubTask] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    # Frontend-specific fields
    domain: Optional[str] = None
    needsClarification: bool = False
    clarificationPrompt: Optional[str] = None
    clarificationResponse: Optional[str] = None
    timestamp: Optional[str] = None