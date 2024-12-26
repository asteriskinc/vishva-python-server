# orcs-v2/core.py
from typing import Dict, List
from datetime import datetime
import asyncio
from openai import AsyncOpenAI, OpenAI
from .types import Task, SubTask, TaskResult, TaskStatus, Agent, TaskDependency
from .orchestration_agents import PlannerAgent

class ORCS:
    def __init__(self, api_key: str):
        self.tasks: Dict[str, Task] = {}  # Changed to dict for easier lookup
        self.completed_results: Dict[str, TaskResult] = {}  # Store results by subtask_id
        self.client = AsyncOpenAI(api_key=api_key)  # Store OpenAI client
        self.planner: Agent = PlannerAgent # main agent that will be used to plan subtasks and assign them to other agents. 
        self.agents: Dict[str, Agent] = {} # dictionary of all agents ORCS has at its disposal. 

    def convert_query_to_task(self, user_query: str) -> Task:
        """
        This function will take a user query and return a Task object for our agents to work on. This is where the planner agent and the dependency determination agent will be used. 
        """
        pass 

    def get_dependencies(self, task: Task) -> List[TaskDependency]:
        """
        This function will take a Task object and return a list of TaskDependency objects for each subtask present in the task. 
        To be used by convert_query_to_task() method. 
        """
        pass 

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

