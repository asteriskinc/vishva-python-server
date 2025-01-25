# orcs/tool_manager.py
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints
from pydantic import BaseModel, create_model
import inspect
import json
from functools import wraps
from .orcs_types import Agent

class ToolRegistry:
    """Registry for managing tool functions and their metadata."""
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.functions: Dict[str, Callable] = {}
    
    def register(self, description: str, strict: bool = True):
        """
        Decorator to register a function as a tool.
        
        Example usage:
        @tool_registry.register(description="Get weather for coordinates")
        async def get_weather(latitude: float, longitude: float) -> WeatherResponse:
            ...
        """
        def decorator(func: Callable):
            # Get function signature info
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)
            
            # Create parameter properties
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                param_type = type_hints.get(param_name, Any)
                
                # Handle Pydantic models in parameters
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    properties[param_name] = {
                        "type": "object",
                        **param_type.model_json_schema()
                    }
                else:
                    # Map Python types to JSON schema types
                    type_map = {
                        int: {"type": "integer"},
                        float: {"type": "number"},
                        str: {"type": "string"},
                        bool: {"type": "boolean"},
                        list: {"type": "array"},
                        dict: {"type": "object"}
                    }
                    properties[param_name] = type_map.get(param_type, {"type": "string"})
                    
                    # Add description if available from docstring
                    if func.__doc__:
                        param_desc = inspect.Parameter.empty
                        for line in func.__doc__.split('\n'):
                            if f'{param_name}:' in line:
                                param_desc = line.split(':', 1)[1].strip()
                                properties[param_name]["description"] = param_desc
                
                # Add to required list if no default value
                if param.default == param.empty:
                    required.append(param_name)
            
            # Create the OpenAI tool schema
            tool_schema = {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }
            
            # Store the tool schema and function
            self.tools[func.__name__] = tool_schema
            self.functions[func.__name__] = func
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def get_agent_tools(self, agent: Agent) -> List[Dict[str, Any]]:
        """Get tools by function names in OpenAI format."""
        return [self.tools[name] for name in agent.tools.keys() if name in self.tools]
    
    async def execute_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """Execute a registered tool by name with given parameters."""
        if name not in self.functions:
            raise ValueError(f"Tool '{name}' not found")
            
        func = self.functions[name]
        result = await func(**params)
        
        # If result is a Pydantic model, convert to dict
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result
    
    async def process_openai_response(self, response: Any) -> Optional[Dict[str, Any]]:
        """
        Process an OpenAI API response containing tool calls.
        Returns the tool execution results if any tools were called.
        """
        message = response.choices[0].message
        
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return None
            
        results = {}
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
                result = await self.execute_tool(func_name, arguments)
                results[tool_call.id] = {
                    "name": func_name,
                    "result": result
                }
            except Exception as e:
                results[tool_call.id] = {
                    "name": func_name,
                    "error": str(e)
                }
                
        return results

# Global tool registry instance
tool_registry = ToolRegistry()