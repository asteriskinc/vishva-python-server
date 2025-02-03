# orcs/core.py
import uuid, json, asyncio
from typing import Any, Dict, List
from datetime import datetime
from openai import AsyncOpenAI
from .orcs_types import AgentTool, DictList, Task, SubTask, TaskResult, TaskStatus, Agent, TaskDependency, ToolCallResult
from .orchestration_agents import PlannerAgent, DependencyAgent
from .execution_agents import EXECUTION_AGENTS
from .tool_manager import tool_registry



class ORCS:
    """
    ORCS is a task orchestration system that uses OpenAI's GPT-4o-mini model to plan and execute tasks.
    """
    def __init__(self, api_key: str):
        self.tasks: Dict[str, Task] = {}  # Changed to dict for easier lookup
        self.completed_results: Dict[str, TaskResult] = {}  # Store results by subtask_id
        self.client = AsyncOpenAI(api_key=api_key)  # Store OpenAI client
        self.planner: Agent = PlannerAgent
        self.dependency_agent: Agent = DependencyAgent
        self.agents: Dict[str, Agent] = EXECUTION_AGENTS  # dictionary of all execution agents
        self.tool_registry = tool_registry

    async def convert_query_to_task(self, user_query: str) -> Task:
        """
        Convert a user query into a Task object using the planner agent.
        """
        # Create a unique task ID
        task_id = str(uuid.uuid4())

        # Get available agent names for validation
        available_agents = list(self.agents.keys())
        
        # Create a more explicit instruction about available agents
        agent_instruction = (
            "IMPORTANT: You MUST ONLY use agents from this list. Do not invent or suggest other agents:\n" +
            "\n".join([f"- {agent.name}: {agent.instructions}" for agent in self.agents.values()])
        )

        # Get planner response using parse
        completion = await self.client.beta.chat.completions.parse(
            model=self.planner.model,
            messages=[
                {"role": "system", "content": self.planner.instructions},
                {"role": "system", "content": agent_instruction},
                {"role": "user", "content": user_query},
            ],
            response_format=self.planner.response_format,
        )

        # Get the parsed response
        planner_output = completion.choices[0].message.parsed

        # Validate and filter subtasks
        subtasks = []
        invalid_agents = []
        
        for idx, subtask_data in enumerate(planner_output.subtasks):
            agent_name = subtask_data.agent
            agent = self.agents.get(agent_name)
            
            if not agent:
                invalid_agents.append(agent_name)
                continue

            subtask = SubTask(
                subtask_id=f"{task_id}_sub_{idx}",
                task_id=task_id,
                agent=agent,
                title=subtask_data.title,
                detail=subtask_data.detail,
                category=subtask_data.category,
                status=TaskStatus.PENDING,
            )
            subtasks.append(subtask)

        # If invalid agents were found, create a new task with clarification
        if invalid_agents:
            error_msg = (
                f"I noticed a request for unavailable agents: {', '.join(invalid_agents)}. "
                f"I can only work with these agents: {', '.join(available_agents)}. "
                "Could you please rephrase your request to use these available services?"
            )
            
            # Create a task with clarification needed
            task = Task(
                task_id=task_id,
                query=user_query,
                subtasks=[],  # No subtasks until clarification
                status=TaskStatus.PENDING,
                start_time=datetime.now().isoformat(),
                domain=planner_output.domain,
                needsClarification=True,
                clarificationPrompt=error_msg,
                timestamp="Just now"
            )
            
            self.tasks[task_id] = task
            return task

        # Create the task object with valid subtasks
        task = Task(
            task_id=task_id,
            query=user_query,
            subtasks=subtasks,
            status=TaskStatus.PENDING,
            start_time=datetime.now().isoformat(),
            domain=planner_output.domain,
            needsClarification=planner_output.needsClarification,
            clarificationPrompt=planner_output.clarificationPrompt,
            timestamp="Just now"
        )

        # Only get dependencies if we have valid subtasks
        if subtasks:
            dependencies = await self.get_dependencies(task, planner_output)
            subtask_dict = {subtask.subtask_id: subtask for subtask in task.subtasks}
            for dep in dependencies:
                if dep.subtask_id in subtask_dict:
                    subtask_dict[dep.subtask_id].dependencies.append(dep)

        # Store the task
        self.tasks[task_id] = task
        return task

    async def get_dependencies(self, task: Task, planner_output: dict) -> List[TaskDependency]:
        """
        Analyze a task's subtasks and determine their dependencies using the dependency agent.
        """
        # Prepare input data for dependency agent
        dependency_input = {
            "task_id": task.task_id,
            "domain": planner_output.domain,
            "subtasks": [
                {
                    "subtask_id": subtask.subtask_id,
                    "title": subtask.title,
                    "agent": subtask.agent.name,
                    "detail": subtask.detail,
                }
                for subtask in task.subtasks
            ],
        }

        # Get dependency analysis using parse
        completion = await self.client.beta.chat.completions.parse(
            model=self.dependency_agent.model,
            messages=[
                {"role": "system", "content": self.dependency_agent.instructions},
                {"role": "user", "content": json.dumps(dependency_input)},
            ],
            response_format=self.dependency_agent.response_format,
        )

        # Get the parsed response
        dependency_output = completion.choices[0].message.parsed

        # Convert to TaskDependency objects
        dependencies = []
        for dep_info in dependency_output.subtask_dependencies:
            if dep_info.depends_on:  # Only create dependency if there is one
                dependency = TaskDependency(
                    task_id=dep_info.depends_on,  # The ID of the task this depends on
                    subtask_id=dep_info.subtask_id,  # The ID of the dependent task
                )
                dependencies.append(dependency)

        return dependencies
    
    def print_dependency_structure(self, task_id: str) -> None:
        """
        Print a hierarchical visualization of the dependency structure for a given task.
        
        Args:
            task_id (str): The ID of the task to visualize
        """
        def get_dependent_tasks(subtask_id: str) -> List[str]:
            """Get all subtasks that depend on the current subtask."""
            dependents = []
            for st in task.subtasks:
                for dep in st.dependencies:
                    if dep.task_id == subtask_id:
                        dependents.append(st.subtask_id)
            return dependents
        
        def print_subtask_tree(subtask_id: str, level: int = 0, visited: set = None):
            """Recursively print the subtask tree."""
            if visited is None:
                visited = set()
                
            if subtask_id in visited:
                return
                
            visited.add(subtask_id)
            
            # Find the actual subtask
            subtask = next((st for st in task.subtasks if st.subtask_id == subtask_id), None)
            if not subtask:
                return
            
            # Print current subtask with proper indentation
            prefix = "│   " * level
            dependencies_str = ""
            if subtask.dependencies:
                deps = [f"{dep.task_id}" for dep in subtask.dependencies]
                dependencies_str = f" (depends on: {', '.join(deps)})"
                
            print(f"{prefix}├── {subtask.title}{dependencies_str}")
            print(f"{prefix}│   └── ID: {subtask.subtask_id}")
            
            # Print status if not pending
            if subtask.status != TaskStatus.PENDING:
                print(f"{prefix}│   └── Status: {subtask.status.value}")
            
            # Recursively print dependent tasks
            dependent_tasks = get_dependent_tasks(subtask_id)
            for dep_id in dependent_tasks:
                print_subtask_tree(dep_id, level + 1, visited)

        # Get the task
        task = self.tasks.get(task_id)
        if not task:
            print(f"No task found with ID: {task_id}")
            return
        
        print(f"\nDependency Structure for Task [{task_id}]:")
        print("=======================================")
        
        # Find and print root tasks (those with no dependencies)
        root_tasks = [st.subtask_id for st in task.subtasks if not st.dependencies]
        
        # If no root tasks found, print all tasks as they might be circular
        if not root_tasks:
            root_tasks = [task.subtasks[0].subtask_id] if task.subtasks else []
            
        # Print the tree starting from each root task
        for root_id in root_tasks:
            print_subtask_tree(root_id)
        
        print("=======================================\n")

    async def execute_task(self, task: Task, status_callback=None) -> TaskResult:
        """
        Execute a complete task by managing subtasks completions according to their dependencies.
        """
        print(f"\nExecuting task with {len(task.subtasks)} subtasks...")
        
        # Start the task
        task.status = TaskStatus.IN_PROGRESS
        task.start_time = datetime.now().isoformat()
        
        completed_subtasks: List[SubTask] = [] 
        while len(completed_subtasks) < len(task.subtasks):
            # gather all pending subtasks that can be executed
            pending_subtasks = [
                subtask for subtask in task.subtasks 
                if subtask.status == TaskStatus.PENDING and subtask.can_execute(self.completed_results)
            ]
            
            if not pending_subtasks:
                break
            
            # Show which subtasks are being executed
            print(f"\nStarting {len(pending_subtasks)} subtasks:")
            for subtask in pending_subtasks:
                print(f"- {subtask.title}")
                
                # Status update for starting subtask
                if status_callback:
                    await status_callback(
                        subtask.subtask_id, 
                        TaskStatus.IN_PROGRESS,
                        f"Starting subtask: {subtask.title}"
                    )
            
            # execute all pending subtasks in parallel using asyncio
            try:
                tasks = [self.execute_subtask(subtask, status_callback) for subtask in pending_subtasks]
                results = await asyncio.gather(*tasks)
                
                # update subtasks and completed results
                for subtask, result in zip(pending_subtasks, results):
                    completed_subtasks.append(subtask)
                    self.completed_results[subtask.subtask_id] = result
                    subtask.status = TaskStatus.COMPLETED
                    subtask.end_time = result.timestamp
                    print(f"✓ Completed: {subtask.title}")
                    
                    # Status update for completed subtask
                    if status_callback:
                        await status_callback(
                            subtask.subtask_id,
                            TaskStatus.COMPLETED,
                            f"Completed Subtask"
                        )
            
            except Exception as e:
                print(f"\nError executing subtasks: {str(e)}")
                
                # Status update for failed subtasks
                for subtask in pending_subtasks:
                    if subtask.status != TaskStatus.COMPLETED:
                        subtask.status = TaskStatus.FAILED
                        if status_callback:
                            await status_callback(
                                subtask.subtask_id,
                                TaskStatus.FAILED,
                                f"Failed subtask: {subtask.title} - {str(e)}"
                            )
                raise
        
        # task is complete
        task.status = TaskStatus.COMPLETED
        task.end_time = datetime.now().isoformat()
        
        print(f"\nTask completed ({len(completed_subtasks)}/{len(task.subtasks)} subtasks)")
        return TaskResult(
            status=TaskStatus.COMPLETED,
            data={"completed_subtasks": completed_subtasks},
            message=f"Task completed with {len(completed_subtasks)} subtasks",
            timestamp=task.end_time,
        )

    async def execute_subtask(self, subtask: SubTask, status_callback=None) -> TaskResult:
        """
        Execute a single subtask using its assigned agent, maintaining interaction history
        and handling multiple rounds of tool calls until completion or max iterations.
        """
        MAX_ITERATIONS = 10  # Consider making this configurable per agent or task type
        
        subtask.status = TaskStatus.IN_PROGRESS
        subtask.start_time = datetime.now().isoformat()
        agent: Agent = subtask.agent
        collected_data = {}
        
        try:
            tools = self.tool_registry.get_agent_tools(agent)
            
            if status_callback:
                await status_callback(
                    subtask.subtask_id,
                    TaskStatus.IN_PROGRESS,
                    f"Agent {agent.name} is analyzing the task..."
                )

            subtask_dependencies = [dep.subtask_id for dep in subtask.dependencies]
            messages = [
                {"role": "system", "content": agent.instructions},
                {"role": "user", "content": f"""Execute the following subtask: {subtask.title}

    Detailed Instructions: {subtask.detail}

    Prior Task Context:
    {self.tasks[subtask.task_id].get_context(subtask_dependencies)}"""}
            ]

            iteration = 0
            while iteration < MAX_ITERATIONS:
                iteration += 1
                
                if status_callback:
                    await status_callback(
                        subtask.subtask_id,
                        TaskStatus.IN_PROGRESS,
                        f"{agent.name} agent is thinking..."
                    )

                completion = await self.client.chat.completions.create(
                    model=agent.model,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice=agent.tool_choice if agent.tool_choice else "auto"
                )

                response = completion.choices[0].message

                if response.content:
                    subtask.add_interaction(
                        agent_name=agent.name,
                        content=response.content
                    )

                # Handle tool calls if any
                new_messages, tool_results = await self._handle_tool_calls(
                    subtask, 
                    response, 
                    collected_data, 
                    status_callback
                )
                messages.extend(new_messages)

                # If no tool calls, try to finalize the response
                if not tool_results:
                    try:
                        return await self._finalize_response(
                            subtask,
                            messages,
                            collected_data,
                            response,
                            status_callback
                        )
                    except Exception as parsing_error:
                        raise parsing_error

                if iteration == MAX_ITERATIONS:
                    # Include all collected data in the error result
                    max_iter_result = TaskResult(
                        status=TaskStatus.FAILED,
                        data={
                            'tool_call_history': collected_data,
                            'iterations_completed': iteration,
                            'final_message': response.content if response.content else None
                        },
                        message=f"Maximum iterations ({MAX_ITERATIONS}) reached",
                        timestamp=datetime.now().isoformat()
                    )
                    
                    subtask.status = TaskStatus.FAILED
                    subtask.end_time = datetime.now().isoformat()
                    subtask.result = max_iter_result

                    if status_callback:
                        await status_callback(
                            subtask.subtask_id,
                            TaskStatus.FAILED,
                            f"Task ended after {MAX_ITERATIONS} iterations"
                        )
                        
                    raise ValueError(f"Maximum iterations ({MAX_ITERATIONS}) reached", max_iter_result)

        except Exception as e:
            error_msg = f"Error in subtask '{subtask.title}': {str(e)}"
            
            # Create an error result that includes all collected data
            error_result = TaskResult(
                status=TaskStatus.FAILED,
                data={
                    'tool_call_history': collected_data,
                    'error_details': str(e),
                    'iterations_completed': iteration if 'iteration' in locals() else 0
                },
                message=error_msg,
                timestamp=datetime.now().isoformat()
            )
            
            if status_callback:
                await status_callback(
                    subtask.subtask_id,
                    TaskStatus.FAILED,
                    error_msg
                )
            
            subtask.add_interaction(
                agent_name="system",
                content=f"Error: {error_msg}"
            )
            
            subtask.status = TaskStatus.FAILED
            subtask.end_time = datetime.now().isoformat()
            subtask.result = error_result
            
            raise ValueError(error_msg, error_result)
        
    async def _handle_tool_calls(
        self,
        subtask: SubTask,
        response,
        collected_data: dict,
        status_callback=None
    ) -> tuple[list, list]:
        """
        Handle tool calls for a subtask execution.
        
        Args:
            subtask: The subtask being executed
            response: The OpenAI API response containing tool calls
            collected_data: Dictionary to store tool call results
            status_callback: Optional callback for status updates
        
        Returns:
            tuple containing:
            - List of message objects to extend the conversation
            - List of tool results
        """
        tool_results = []
        messages_to_add = []
        
        if not hasattr(response, 'tool_calls') or not response.tool_calls:
            return [], []
            
        for tool_call in response.tool_calls:
            if status_callback:
                await status_callback(
                    subtask.subtask_id,
                    TaskStatus.IN_PROGRESS,
                    f"Using {tool_call.function.name} to gather information...",
                    content={
                        "type": "tool_call_start",
                        "data": {
                            "tool": tool_call.function.name,
                            "arguments": json.loads(tool_call.function.arguments)
                        }
                    }
                )
            
            try:
                tool_result = await self._execute_tool_call(tool_call)
                tool_results.append(tool_result)
                
                # Store tool call results regardless of error status
                collected_data[tool_call.function.name] = {
                    'result': tool_result.result.to_dict(),
                    'error': tool_result.error,
                    'timestamp': tool_result.timestamp
                }
                
                if status_callback:
                    await status_callback(
                        subtask.subtask_id,
                        TaskStatus.IN_PROGRESS,
                        f"Information gathered from {tool_call.function.name}",
                        content={
                            "type": "tool_result",
                            "data": {
                                "tool": tool_call.function.name,
                                "result": tool_result.result.to_dict(),
                                "error": tool_result.error
                            }
                        }
                    )
                    
            except Exception as e:
                error_msg = f"Error using {tool_call.function.name}: {str(e)}"
                if status_callback:
                    await status_callback(
                        subtask.subtask_id,
                        TaskStatus.IN_PROGRESS,
                        error_msg,
                        content={
                            "type": "tool_call_error",
                            "data": {
                                "tool": tool_call.function.name,
                                "error": str(e)
                            }
                        }
                    )
                tool_result = ToolCallResult(
                    tool_name=tool_call.function.name,
                    arguments=DictList(items=[]),
                    result=DictList(items=[]),
                    error=str(e),
                    timestamp=datetime.now().isoformat()
                )
                tool_results.append(tool_result)

        if tool_results:
            subtask.add_interaction(
                agent_name="system",
                content="Tool execution results",
                tool_calls=tool_results
            )

            messages_to_add = [
                {
                    "role": "assistant",
                    "content": response.content if response.content else "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in response.tool_calls
                    ]
                },
                *[{
                    "role": "tool",
                    "content": json.dumps(tr.result.to_dict()),
                    "tool_call_id": tc.id
                } for tr, tc in zip(tool_results, response.tool_calls)]
            ]
        
        return messages_to_add, tool_results
    
    async def _execute_tool_call(self, tool_call: Any) -> ToolCallResult:
        try:
            tool_name = tool_call.function.name
            
            if tool_name not in self.tool_registry.functions:
                raise ValueError(f"Tool '{tool_name}' not found in registry")
                
            tool_func = self.tool_registry.functions[tool_name]
            arguments = json.loads(tool_call.function.arguments)
            
            arguments_dict = DictList(items=[
                DictList.Item(key=k, value=str(v))
                for k, v in arguments.items()
            ])
            
            print(f"\nExecuting tool: {tool_name}")
            print(f"Arguments: {arguments}")
            
            result = await tool_func(**arguments)
            result_dict = result.model_dump()
            
            # Special handling for enhanced web search results
            if tool_name == "enhanced_web_search":
                # Convert the enhanced search results to a more detailed format
                result_dict_list = DictList(items=[
                    DictList.Item(key=k, value=str(v))
                    for result in result_dict['results']
                    for k, v in {
                        'title': result['title'],
                        'url': result['url'],
                        'summary': result['summary'],
                        'content': result['content'][:1000] + '...' if len(result['content']) > 1000 else result['content'],
                        'source': result['source'],
                        'metadata': json.dumps({
                            k: v for k, v in result['metadata'].items()
                            if k in ['status_code', 'redirected_url']
                        })
                    }.items()
                ])
            else:
                result_dict_list = DictList(items=[
                    DictList.Item(key=k, value=str(v))
                    for k, v in result_dict.items()
                ])
            
            return ToolCallResult(
                tool_name=tool_name,
                arguments=arguments_dict,
                result=result_dict_list,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_call.function.name}: {str(e)}"
            print(f"Tool execution failed: {error_msg}")
            
            return ToolCallResult(
                tool_name=tool_call.function.name,
                arguments=arguments_dict if 'arguments_dict' in locals() else DictList(items=[]),
                result=DictList(items=[]),
                error=error_msg,
                timestamp=datetime.now().isoformat()
            )
            
    async def _finalize_response(
            self,
            subtask: SubTask,
            messages: list,
            collected_data: dict,
            response,
            status_callback=None
        ) -> TaskResult:
            """
            Finalize the response for a subtask execution.
            
            Args:
                subtask: The subtask being executed
                messages: List of conversation messages
                collected_data: Dictionary of collected tool call data
                response: The OpenAI API response
                status_callback: Optional callback for status updates
                
            Returns:
                TaskResult containing the final structured response
            """
            if status_callback:
                await status_callback(
                    subtask.subtask_id,
                    TaskStatus.IN_PROGRESS,
                    "Finalizing results...",
                    content={
                        "type": "agent_response",
                        "data": {
                            "role": "assistant",
                            "content": response.content if response.content else "",
                        }
                    }
                )
            
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            
            final_completion = await self.client.beta.chat.completions.parse(
                model=subtask.agent.model,
                messages=messages,
                response_format=subtask.agent.response_format
            )
            
            structured_response = final_completion.choices[0].message.parsed
            subtask.add_interaction(
                agent_name=subtask.agent.name,
                content=f"Final Structured Response: {json.dumps(structured_response.model_dump())}"
            )
            
            task_result = TaskResult(
                status=TaskStatus.COMPLETED,
                data={
                    'final_response': structured_response.model_dump(),
                    'tool_call_history': collected_data
                },
                message="Task completed successfully",
                timestamp=datetime.now().isoformat()
            )
            
            subtask.status = TaskStatus.COMPLETED
            subtask.end_time = datetime.now().isoformat()
            subtask.result = task_result
            
            if status_callback:
                await status_callback(
                    subtask.subtask_id,
                    TaskStatus.COMPLETED,
                    "Task completed successfully!"
                )
            
            return task_result
