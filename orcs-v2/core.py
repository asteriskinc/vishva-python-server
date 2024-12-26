# orcs-v2/core.py
from typing import Dict, List
from datetime import datetime
from openai import AsyncOpenAI
from orcs_types import Task, SubTask, TaskResult, TaskStatus, Agent, TaskDependency
from orchestration_agents import PlannerAgent, DependencyAgent
import uuid, json

class ORCS:
    def __init__(self, api_key: str):
        self.tasks: Dict[str, Task] = {}  # Changed to dict for easier lookup
        self.completed_results: Dict[str, TaskResult] = {}  # Store results by subtask_id
        self.client = AsyncOpenAI(api_key=api_key)  # Store OpenAI client
        self.planner: Agent = PlannerAgent # main agent that will be used to plan subtasks
        self.dependency_agent: Agent = DependencyAgent # agent for determining dependencies
        self.agents: Dict[str, Agent] = {} # dictionary of all execution agents


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
                {
                    "role": "system",
                    "content": self.planner.instructions
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            response_format=self.planner.response_format
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
                status=TaskStatus.PENDING
            )
            subtasks.append(subtask)
        
        # Create the initial task object
        task = Task(
            task_id=task_id,
            subtasks=subtasks,
            status=TaskStatus.PENDING,
            start_time=datetime.now().isoformat()
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
                    "detail": subtask.detail
                }
                for subtask in task.subtasks
            ]
        }
        
        # Get dependency analysis using parse
        completion = await self.client.beta.chat.completions.parse(
            model=self.dependency_agent.model,
            messages=[
                {
                    "role": "system",
                    "content": self.dependency_agent.instructions
                },
                {
                    "role": "user",
                    "content": json.dumps(dependency_input)
                }
            ],
            response_format=self.dependency_agent.response_format
        )
        
        # Get the parsed response
        dependency_output = completion.choices[0].message.parsed
        
        # Convert to TaskDependency objects
        dependencies = []
        for dep_info in dependency_output.subtask_dependencies:
            if dep_info.depends_on:  # Only create dependency if there is one
                dependency = TaskDependency(
                    task_id=dep_info.depends_on,  # The ID of the task this depends on
                    subtask_id=dep_info.subtask_id  # The ID of the dependent task
                )
                dependencies.append(dependency)
        
        return dependencies

    def execute_task(self, task: Task) -> TaskResult:
        """
        This function will take a Task object and execute it. 
        """
        pass 

    def execute_subtask(self, subtask: SubTask) -> TaskResult:
        """
        This function will take a SubTask object and execute it. 
        """
        pass 

    def run_agent_for_subtask(self, subtask: SubTask, agent: Agent) -> TaskResult:
        """
        This function will take a SubTask object and an Agent object and run the agent on the subtask. 
        """
        pass 

