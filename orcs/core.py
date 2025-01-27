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

        # Get planner response using parse
        completion = await self.client.beta.chat.completions.parse(
            model=self.planner.model,
            messages=[
                {"role": "system", "content": self.planner.instructions},
                {"role": "system", "content": "Available Agents and their capabilities:"},
                {"role": "system", "content": "\n".join([f"- {agent.name}: {agent.instructions}" for agent in self.agents.values()])},
                {"role": "user", "content": user_query},
            ],
            response_format=self.planner.response_format,
        )

        # Get the parsed response
        planner_output = completion.choices[0].message.parsed

        # Create subtasks without dependencies initially
        subtasks = []
        for idx, subtask_data in enumerate(planner_output.subtasks):
            # Get the appropriate agent for this subtask
            agent_name = subtask_data.agent
            agent = self.agents.get(agent_name)
            if not agent:
                raise ValueError(f"No agent found for name: {agent_name}")

            subtask = SubTask(
                subtask_id=f"{task_id}_sub_{idx}",
                task_id=task_id,
                agent=agent,
                title=subtask_data.title,
                detail=subtask_data.detail,
                category=subtask_data.category,  # Make sure category is included
                status=TaskStatus.PENDING,
            )
            subtasks.append(subtask)

        # Create the initial task object with the original query
        task = Task(
            task_id=task_id,
            query=user_query,  # Set the original query
            subtasks=subtasks,
            status=TaskStatus.PENDING,
            start_time=datetime.now().isoformat(),
            domain=planner_output.domain,  # Set domain from planner output
            needsClarification=planner_output.needsClarification,  # Set clarification flag
            clarificationPrompt=planner_output.clarificationPrompt,  # Set clarification prompt
            timestamp="Just now"  # Add a basic timestamp
        )

        # Get and set dependencies
        dependencies = await self.get_dependencies(task, planner_output)

        # Update subtasks with their dependencies
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
                tasks = [self.execute_subtask(subtask) for subtask in pending_subtasks]
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
                            f"Completed subtask: {subtask.title}"
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

    async def execute_subtask(self, subtask: SubTask) -> TaskResult:
        """
        Execute a single subtask using its assigned agent, maintaining interaction history
        and handling multiple rounds of tool calls until completion.
        """
        subtask.status = TaskStatus.IN_PROGRESS
        subtask.start_time = datetime.now().isoformat()

        # Get the agent assigned to this subtask
        agent: Agent = subtask.agent
        print(f"Agent assigned to subtask: {agent.name}")
        try:
            # Get the tools available to this agent from registry
            tools = self.tool_registry.get_agent_tools(agent)
            print(f"\nAgent '{agent.name}' executing subtask '{subtask.title}'")
            print(f"Available tools: {[tool['function']['name'] for tool in tools]}")
            subtask_dependencies = [dep.subtask_id for dep in subtask.dependencies]
            # Initialize conversation with task context and instructions
            messages = [
                {
                    "role": "system",
                    "content": agent.instructions
                },
                {
                    "role": "user",
                    "content": f"""Execute the following subtask: {subtask.title}

    Detailed Instructions: {subtask.detail}

    Prior Task Context:
    {self.tasks[subtask.task_id].get_context(subtask_dependencies)}

    You can use the available tools to gather any information needed. Once you have all necessary information,
    provide a detailed summary of your findings. No need for any special indicators - simply stop making
    tool calls when you have everything you need.

    Always explain your thinking and next steps.
    """
                }
            ]

            MAX_ITERATIONS = 20  # Prevent infinite loops
            iteration = 0

            while iteration < MAX_ITERATIONS:
                iteration += 1
                print(f"\nIteration {iteration} of subtask execution")

                # Make API call with tool calling enabled
                completion = await self.client.chat.completions.create(
                    model=agent.model,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice=agent.tool_choice if agent.tool_choice else "auto"
                )

                # Get the response
                response = completion.choices[0].message

                # Only add interaction if there's content to add
                if response.content:
                    subtask.add_interaction(
                        agent_name=agent.name,
                        content=response.content
                    )

                # Check if there are any tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tool_results = []
                    
                    for tool_call in response.tool_calls:
                        print(f"\nExecuting tool call: {tool_call.function.name}")
                        print(f"Arguments: {tool_call.function.arguments}")
                        
                        try:
                            # Execute the tool call
                            tool_result = await self._execute_tool_call(tool_call)
                            tool_results.append(tool_result)
                            
                        except Exception as e:
                            print(f"Error executing tool {tool_call.function.name}: {str(e)}")
                            tool_result = ToolCallResult(
                                tool_name=tool_call.function.name,
                                arguments=DictList(items=[]),
                                result=DictList(items=[]),
                                error=str(e),
                                timestamp=datetime.now().isoformat()
                            )
                            tool_results.append(tool_result)

                    # Only add tool results interaction if there are results
                    if tool_results:
                        subtask.add_interaction(
                            agent_name="system",
                            content="Tool execution results",
                            tool_calls=tool_results
                        )

                    # Add assistant's response and tool calls to conversation
                    assistant_message = {
                        "role": "assistant",
                        "content": response.content if response.content else "",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            } for tool_call in response.tool_calls
                        ]
                    }
                    messages.append(assistant_message)
                    
                    # Add tool results to messages, matching tool_call_id with the original call
                    for tool_result, tool_call in zip(tool_results, response.tool_calls):
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_result.result.to_dict()),
                            "tool_call_id": tool_call.id  # Use the actual tool_call.id
                        })
                else:
                    # No tool calls - agent has finished gathering information
                    # Add the final narrative response to messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    
                    print("\nAgent completed information gathering. Getting structured response...")
                    
                    # Get structured response using parse
                    final_completion = await self.client.beta.chat.completions.parse(
                        model=agent.model,
                        messages=messages,
                        response_format=agent.response_format
                    )
                    
                    structured_response = final_completion.choices[0].message.parsed
                    print(f"\nStructured Response: {structured_response}")

                    # Record the final structured response
                    subtask.add_interaction(
                        agent_name=agent.name,
                        content=f"Final Structured Response: {json.dumps(structured_response.model_dump())}"
                    )

                    # Create final result
                    task_result = TaskResult(
                        status=TaskStatus.COMPLETED,
                        data=structured_response.model_dump(),
                        message="Task completed successfully",
                        timestamp=datetime.now().isoformat()
                    )

                    subtask.status = TaskStatus.COMPLETED
                    subtask.end_time = datetime.now().isoformat()
                    subtask.result = task_result

                    return task_result

                # Check if max iterations reached
                if iteration == MAX_ITERATIONS:
                    print(f"\nReached maximum iterations ({MAX_ITERATIONS})")
                    subtask.add_interaction(
                        agent_name="system",
                        content="Task incomplete: Maximum iterations reached"
                    )
                    raise ValueError("Maximum iterations reached without completion")

            return TaskResult(
                status=TaskStatus.FAILED,
                data={},
                message="Task did not reach completion state",
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            error_msg = f"Error in subtask '{subtask.title}': {str(e)}"
            print(error_msg)
            
            # Record the error in history
            subtask.add_interaction(
                agent_name="system",
                content=f"Error: {error_msg}"
            )
            
            subtask.status = TaskStatus.FAILED
            subtask.end_time = datetime.now().isoformat()
            
            raise ValueError(error_msg)
        
    async def _execute_tool_call(
        self,
        tool_call: Any
    ) -> ToolCallResult:
        """
        Execute a tool call using the registered function from tool registry.
        Each tool returns a well-defined Pydantic model that we can convert to dict.
        
        Args:
            tool_call: The tool call from the OpenAI API response
                
        Returns:
            ToolCallResult containing the execution results
        """
        try:
            tool_name = tool_call.function.name
            
            # Check if tool exists in registry
            if tool_name not in self.tool_registry.functions:
                raise ValueError(f"Tool '{tool_name}' not found in registry")
                
            # Get the actual function from registry
            tool_func = self.tool_registry.functions[tool_name]
            
            # Parse the arguments from the tool call
            arguments = json.loads(tool_call.function.arguments)
            
            # Convert arguments to DictList format for storage
            arguments_dict = DictList(items=[
                DictList.Item(key=k, value=str(v))
                for k, v in arguments.items()
            ])
            
            print(f"\nExecuting tool: {tool_name}")
            print(f"Arguments: {arguments}")
            
            # Execute the tool function and convert result to dict
            result = await tool_func(**arguments)
            result_dict = result.model_dump()
            
            # print some of the metadata like title, url, source, snippet and a small sample of the content
            print(f"Title: {result_dict['title']}")
            print(f"URL: {result_dict['url']}")
            print(f"Source: {result_dict['source']}")
            print(f"Snippet: {result_dict['snippet']}")
            print(f"Content: {result_dict['content'][:100]}...")
            
            # Convert result to DictList format
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