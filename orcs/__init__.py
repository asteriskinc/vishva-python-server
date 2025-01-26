# orcs/__init__.py
from .core import ORCS
from .execution_agents import EXECUTION_AGENTS
from .orchestration_agents import PlannerAgent, DependencyAgent
from .orcs_types import (
    Task, 
    SubTask, 
    TaskResult, 
    TaskStatus, 
    Agent, 
    TaskDependency,
    ToolCallResult,
    AgentInteraction,
    DictList
)
from .tool_manager import tool_registry
from .tools.web_tools import web_search, get_distance_matrix, get_directions

__all__ = [
    # Core components
    'ORCS',
    'EXECUTION_AGENTS',
    'PlannerAgent',
    'DependencyAgent',
    
    # Type definitions
    'Task',
    'SubTask',
    'TaskResult',
    'TaskStatus',
    'Agent',
    'TaskDependency',
    'ToolCallResult',
    'AgentInteraction',
    'DictList',
    
    # Tool management
    'tool_registry',
    
    # Web tools
    'web_search',
    'get_distance_matrix',
    'get_directions'
]