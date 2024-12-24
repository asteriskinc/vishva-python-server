# orcs-v2/core.py
from pydantic import BaseModel, Field
from typing import Callable, Type, Dict, Optional, List, Any
from datetime import datetime
import json
from enum import Enum
import asyncio
from openai import AsyncOpenAI, OpenAI

"""------------Our Core Classes Start Here------------"""

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


class ORCS:
    def __init__(self, api_key: str):
        self.tasks: Dict[str, Task] = {}  # Changed to dict for easier lookup
        self.completed_results: Dict[str, TaskResult] = {}  # Store results by subtask_id
        self.client = AsyncOpenAI(api_key=api_key)  # Store OpenAI client

    def _gather_dependency_data(self, subtask: SubTask) -> dict:
        """Gather data from dependent tasks"""
        input_data = {}
        for dependency in subtask.dependencies:
            dep_key = f"{dependency.task_id}_{dependency.subtask_id}"
            if dep_key in self.completed_results:
                input_data.update(self.completed_results[dep_key].data)
        return input_data

    async def _execute_subtask(self, task_id: str, subtask: SubTask) -> TaskResult:
        """Execute a subtask and return the result"""
        try:
            subtask.status = TaskStatus.IN_PROGRESS
            subtask.start_time = datetime.now().isoformat()

            # Gather dependency data
            input_data = self._gather_dependency_data(subtask)
            messages = subtask.agent.prepare_messages(input_data)

            # Prepare API call parameters
            params = {
                "model": subtask.agent.model,
                "messages": messages,
            }

            # Add tools if specified
            if subtask.agent.tools:
                params["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": "Execute function",
                            "parameters": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    } for name in subtask.agent.tools.keys()
                ]
                if subtask.agent.tool_choice:
                    params["tool_choice"] = {
                        "type": "function", 
                        "function": {"name": subtask.agent.tool_choice}
                    }
            
            if subtask.agent.response_format:
                params["response_format"] = {"type": "json_object"}

            # Make API call
            response = await self.client.chat.completions.create(**params)
            
            # Process response and execute tools if needed
            result_data = subtask.agent.process_response(response)
            
            # Create task result
            result = TaskResult(
                status=TaskStatus.COMPLETED,
                data=result_data,
                message=response.choices[0].message.content,
                timestamp=datetime.now().isoformat()
            )

            # Update agent conversation history
            subtask.agent.update_conversation_history(input_data, result_data)

            # Update subtask status
            subtask.status = TaskStatus.COMPLETED
            subtask.end_time = datetime.now().isoformat()
            subtask.result = result
            
            # Store result for dependency resolution
            self.completed_results[f"{task_id}_{subtask.subtask_id}"] = result
            
            return result

        except Exception as e:
            error_result = TaskResult(
                status=TaskStatus.FAILED,
                data={},
                message=str(e),
                timestamp=datetime.now().isoformat()
            )
            
            subtask.status = TaskStatus.FAILED
            subtask.end_time = datetime.now().isoformat()
            subtask.result = error_result
            
            return error_result

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute a task and all its subtasks"""
        try:
            # Initialize task execution
            task.status = TaskStatus.IN_PROGRESS
            task.start_time = datetime.now().isoformat()
            self.tasks[task.task_id] = task
            
            # Track attempted and completed subtasks
            attempted_subtasks = set()
            completed_results = []
            
            while len(attempted_subtasks) < len(task.subtasks):
                # Find executable subtasks
                executable_subtasks = [
                    subtask for subtask in task.subtasks
                    if subtask.subtask_id not in attempted_subtasks 
                    and subtask.can_execute(self.completed_results)
                ]
                
                if not executable_subtasks:
                    remaining_subtasks = [
                        t for t in task.subtasks 
                        if t.subtask_id not in attempted_subtasks
                    ]
                    raise Exception(
                        f"Unable to resolve dependencies for subtasks: "
                        f"{[t.subtask_id for t in remaining_subtasks]}"
                    )
                
                # Execute subtasks
                execution_tasks = []
                for subtask in executable_subtasks:
                    attempted_subtasks.add(subtask.subtask_id)
                    
                    if subtask.agent.parallel_tool_calls:
                        execution_tasks.append(
                            self._execute_subtask(task.task_id, subtask)
                        )
                    else:
                        result = await self._execute_subtask(task.task_id, subtask)
                        completed_results.append(result)
                
                if execution_tasks:
                    parallel_results = await asyncio.gather(*execution_tasks)
                    completed_results.extend(parallel_results)
            
            # Process results
            failed_results = [
                r for r in completed_results 
                if r.status == TaskStatus.FAILED
            ]
            
            # Create final result
            final_status = (
                TaskStatus.COMPLETED if not failed_results 
                else TaskStatus.FAILED
            )
            
            task_result = TaskResult(
                status=final_status,
                data={
                    "subtask_results": [r.data for r in completed_results],
                    "failed_subtasks": len(failed_results)
                },
                message=(
                    "Task completed successfully" if not failed_results
                    else f"Task failed with {len(failed_results)} subtask failures"
                ),
                timestamp=datetime.now().isoformat()
            )
            
            # Update task status
            task.status = final_status
            task.end_time = datetime.now().isoformat()
            task.result = task_result
            
            return task_result
            
        except Exception as e:
            error_result = TaskResult(
                status=TaskStatus.FAILED,
                data={"error": str(e)},
                message=f"Task failed with error: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
            
            task.status = TaskStatus.FAILED
            task.end_time = datetime.now().isoformat()
            task.result = error_result
            
            return error_result
        
