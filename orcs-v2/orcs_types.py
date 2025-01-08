# orcs-v2/orcs_types.py
import json
from typing import Callable, Type, Dict, Optional, List, Any, Union
from pydantic import BaseModel, Field
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

class Agent(BaseModel): 
    name: str = "Agent" 
    model: str = "gpt-4o-mini"
    instructions: str | Callable[[], str]= "You are a helpful assistant."
    tools: Dict[str, AgentTool] = Field(default_factory=dict)
    tool_choice: Optional[str] | None = None
    parallel_tool_calls: bool = True
    response_format: Union[Type[BaseModel], dict, None] = None

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
    subtasks: List[SubTask] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None