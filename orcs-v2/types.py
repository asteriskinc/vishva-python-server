# orcs-v2/types.py
import json
from typing import Callable, Type, Dict, Optional, List, Any
from pydantic import BaseModel, Field
from enum import Enum

"""------------Our Core Classes and Types Here------------"""

AgentTool = Callable[[], str]

class Agent(BaseModel): 
    name: str = "Agent" 
    model: str = "gpt-4o-mini"
    instructions: str | Callable[[], str]= "You are a helpful assistant."
    tools: Dict[str, AgentTool] = Field(default_factory=dict) # a dictionary of tool names and their corresponding functions
    tool_choice: Optional[str] | None = None # if not None, the agent will only use the tool with this name
    parallel_tool_calls: bool = True # if true, the agent will call tools in parallel
    response_format: Type[BaseModel] | None = None # if not None, the agent will return a response in the format of the response_format

    def prepare_messages(self, input_data: dict) -> List[dict]:
        """Prepare the messages for the API call."""
        messages = [
            {
                "role": "system",
                "content": self.instructions() if callable(self.instructions) else self.instructions
            }
        ]
        messages.extend(self.conversation_history)
        messages.append({
            "role": "user",
            "content": json.dumps(input_data)
        })
        return messages

    def process_response(self, response: Any) -> dict: 
        """Process the response from the API call."""
        message = response.choices[0].message.content

        # Handle tool calls if present 
        if message.tool_calls: 
            results = {}
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                if func_name in self.functions:
                    args = json.loads(tool_call.function.arguments)
                    results[func_name] = self.functions[func_name](args)
            return results
        
        # Handle regular responses
        if self.response_format:
            return json.loads(message.content) 
        
        return {"response": message.content}
    
    def update_conversation_history(self, input_data: dict, result: dict):
        """Update the conversation history with the new message."""
        self.conversation_history.extend([
            {"role": "user", "content": str(input_data)},
            {"role": "assistant", "content": str(result)}
        ])


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
            all(field in completed_tasks[dep.task_id].data for field in dep.required_data)
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

"""------------Our Core Classes End Here------------"""