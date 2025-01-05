# orcs-v2/core.py
from typing import Dict, List
from datetime import datetime
from openai import AsyncOpenAI
from orcs_types import Task, SubTask, TaskResult, TaskStatus, Agent, TaskDependency
from orchestration_agents import PlannerAgent, DependencyAgent
from execution_agents import EXECUTION_AGENTS
import uuid, json, asyncio


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
                status=TaskStatus.PENDING,
            )
            subtasks.append(subtask)

        # Create the initial task object
        task = Task(
            task_id=task_id,
            subtasks=subtasks,
            status=TaskStatus.PENDING,
            start_time=datetime.now().isoformat(),
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

    async def execute_task(self, task: Task) -> TaskResult:
        """
        Execute a complete task by managing subtasks completions according to their dependencies.
        """
        # Start the task
        task.status = TaskStatus.IN_PROGRESS
        task.start_time = datetime.now().isoformat()
        
        completed_subtasks: List[SubTask] = [] 
        while len(completed_subtasks) < len(task.subtasks):
            # gather all pending subtasks that can be executed
            pending_subtasks = [subtask for subtask in task.subtasks if subtask.status == TaskStatus.PENDING and subtask.can_execute(self.completed_results)]
            
            # execute all pending subtasks parallely using asyncio
            tasks = [self.execute_subtask(subtask) for subtask in pending_subtasks]
            results = await asyncio.gather(*tasks)
            
            # update subtasks and completed results
            for subtask, result in zip(pending_subtasks, results):
                completed_subtasks.append(subtask)
                self.completed_results[subtask.subtask_id] = result
                subtask.status = TaskStatus.COMPLETED
                subtask.end_time = result.timestamp
        
        # task is complete
        task.status = TaskStatus.COMPLETED
        task.end_time = datetime.now().isoformat()
        return TaskResult(
            status=TaskStatus.COMPLETED,
            data={"completed_subtasks": completed_subtasks},
            message=f"Task completed with {len(completed_subtasks)} subtasks",
            timestamp=task.end_time,
        )

    async def execute_subtask(self, subtask: SubTask) -> TaskResult:
        """
        Execute a single subtask using its assigned agent.
        """
        subtask.status = TaskStatus.IN_PROGRESS
        subtask.start_time = datetime.now().isoformat()

        # Get the agent assigned to this subtask
        agent: Agent = subtask.agent

        # Prepare the input data for the agent to execute the subtask
        input_data = {
            "subtask_id": subtask.subtask_id,
            "task_id": subtask.task_id,
            "instructions": subtask.detail,
            "title": subtask.title,
            # include all previous subtask results
            "previous_results": [self.completed_results[dep.subtask_id] for dep in subtask.dependencies if dep.subtask_id in self.completed_results],
        }
        
        # Run the agent
        completion = await self.client.beta.chat.completions.parse(
            model=agent.model,
            messages=[
                {
                    "role": "system",
                    "content": agent.instructions
                },
                {
                    "role": "user",
                    "content": json.dumps(input_data)
                }
            ],
            response_format=agent.response_format
        )
        
        # Get the parsed response
        agent_output = completion.choices[0].message.parsed
        
        # Store the result
        result = TaskResult(
            status=TaskStatus.COMPLETED,
            data=agent_output.dict(),
            message=f"Successfully executed {agent.name} for subtask: {subtask.title}",
            timestamp=datetime.now().isoformat()
        )
        
        return result