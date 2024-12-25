# orcs-v2/core.py
from typing import Dict
from datetime import datetime
import asyncio
from openai import AsyncOpenAI, OpenAI
from .types import Task, SubTask, TaskResult, TaskStatus, Agent
from .agents import PlannerAgent

class ORCS:
    def __init__(self, api_key: str):
        self.tasks: Dict[str, Task] = {}  # Changed to dict for easier lookup
        self.completed_results: Dict[str, TaskResult] = {}  # Store results by subtask_id
        self.client = AsyncOpenAI(api_key=api_key)  # Store OpenAI client
        self.planner: Agent = PlannerAgent # main agent that will be used to plan subtasks and assign them to other agents. 
        self.agents: Dict[str, Agent] = {} # dictionary of all agents ORCS has at its disposal. 

    def query_to_task(self, user_query: str) -> Task:
        """
        This function will take a user query and return a task. 
        """
        pass 

    

    