# orcs/orcs_types.py
from typing import Callable, Dict, Optional, List, Any, Union
from pydantic import BaseModel, Field, model_serializer
from enum import Enum
from datetime import datetime

"""------------Dict Format for OpenAI Compatibility------------"""
class DictList(BaseModel):
    class Item(BaseModel):
        key: str
        value: str
    items: List[Item]
    
    def to_dict(self):
        return {item.key: item.value for item in self.items}

"""------------Interaction and Tool Call Types------------"""
class ToolCallResult(BaseModel):
    """Records a tool call and its result"""
    tool_name: str
    arguments: DictList
    result: DictList
    timestamp: str
    error: Optional[str] = None

    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments.to_dict(),
            "result": self.result.to_dict(),
            "timestamp": self.timestamp,
            "error": self.error
        }

class AgentInteraction(BaseModel):
    """Records an agent's interaction in a conversation"""
    agent_name: str
    role: str = "assistant"
    content: str
    tool_calls: Optional[List[ToolCallResult]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

"""------------Core Types------------"""
AgentTool = Callable[[], DictList]

class Agent(BaseModel): 
    name: str = "Agent" 
    model: str = "gpt-4o-mini"
    instructions: str | Callable[[], str] = "You are a helpful assistant."
    tools: Dict[str, AgentTool] = Field(default_factory=dict)
    tool_choice: Optional[str] | None = None
    parallel_tool_calls: bool = True
    response_format: Any = None
    
    @model_serializer
    def serialize_model(self) -> dict:
        """Custom serialization for Agent class"""
        return {
            "name": self.name,
            "model": self.model,
            "instructions": self.instructions if isinstance(self.instructions, str) else self.instructions(),
            "tool_choice": self.tool_choice,
            "parallel_tool_calls": self.parallel_tool_calls,
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
    # History tracking
    history: List[AgentInteraction] = Field(default_factory=list)
    
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

    def add_interaction(
        self, 
        agent_name: str, 
        content: str, 
        tool_calls: Optional[List[ToolCallResult]] = None
    ) -> AgentInteraction:
        """Add a new interaction to the subtask history"""
        interaction = AgentInteraction(
            agent_name=agent_name,
            content=content,
            tool_calls=tool_calls,
            timestamp=datetime.now().isoformat()
        )
        self.history.append(interaction)
        return interaction

    def get_formatted_history(self) -> str:
        """Get a formatted string of the interaction history"""
        formatted_lines = []
        
        # Add interaction history
        formatted_lines.append(f"History for subtask '{self.title}':")
        for interaction in self.history:
            formatted_lines.append(f"[{interaction.timestamp}] {interaction.agent_name}:")
            formatted_lines.append(interaction.content)
            
            if interaction.tool_calls:
                for tool_call in interaction.tool_calls:
                    formatted_lines.append(f"Tool Call: {tool_call.tool_name}")
                    formatted_lines.append(f"Arguments: {tool_call.arguments.to_dict()}")
                    formatted_lines.append(f"Result: {tool_call.result.to_dict()}")
                    if tool_call.error:
                        formatted_lines.append(f"Error: {tool_call.error}")
            formatted_lines.append("")
            
        return "\n".join(formatted_lines)

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

    def get_context(self, subtask_ids: List[str] = []) -> str:
        """
        Get the complete context of the task by aggregating all subtask histories.
        This includes all agent interactions, tool calls, and results across all subtasks.
        """
        context_lines = [
            f"Task Context for '{self.query}'",
            f"Status: {self.status.value}",
            f"Domain: {self.domain}",
            ""
        ]

        # Add clarification information if present
        if self.needsClarification:
            context_lines.extend([
                "Clarification Required:",
                f"Prompt: {self.clarificationPrompt}",
                f"Response: {self.clarificationResponse or 'Not provided'}",
                ""
            ])

        if subtask_ids:
            filtered_subtasks = [subtask for subtask in self.subtasks if subtask.subtask_id in subtask_ids]
        else:
            filtered_subtasks = self.subtasks

        # Add each subtask's history
        for subtask in filtered_subtasks:
            context_lines.extend([
                f"=== Subtask: {subtask.title} ===",
                f"Status: {subtask.status.value}",
                f"Agent: {subtask.agent.name}",
                ""
            ])
            
            # Add dependencies if any
            if subtask.dependencies:
                context_lines.append("Dependencies:")
                for dep in subtask.dependencies:
                    context_lines.append(f"- Depends on subtask: {dep.subtask_id}")
                context_lines.append("")

            # Add the subtask's interaction history
            if subtask.history:
                context_lines.extend(subtask.get_formatted_history().split('\n'))
            else:
                context_lines.append("No interactions recorded yet.")
            
            context_lines.append("\n")  # Extra spacing between subtasks

        return "\n".join(context_lines)