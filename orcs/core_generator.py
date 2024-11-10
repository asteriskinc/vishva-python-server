import copy
import json
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Generator, Any
from enum import Enum

from openai import OpenAI

from .util import function_to_json, debug_print, merge_chunk
from .types import (
    Agent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Function,
    Response,
    Result,
)

class AgentEventType(Enum):
    AGENT_START = "agent_start"
    AGENT_THINKING = "agent_thinking"
    AGENT_GENERATING = "agent_generating"
    AGENT_GENERATED = "agent_generated"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    AGENT_HANDOFF = "agent_handoff"
    AGENT_COMPLETE = "agent_complete"

class AgentEvent:
    def __init__(
        self,
        type: AgentEventType,
        agent_name: str,
        data: Dict[str, Any] = None,
        timestamp: str = None
    ):
        self.type = type
        self.agent_name = agent_name
        self.data = data or {}
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "data": {
                "agent": {
                    "name": self.agent_name,
                    "currentTask": self.data.get("currentTask")
                },
                **self.data
            },
            "timestamp": self.timestamp
        }

class Orcs:
    def __init__(self, client=None):
        if not client:
            client = OpenAI()
        self.client = client

    def get_chat_completion(
        self,
        agent: Agent,
        history: List,
        context_variables: dict,
        model_override: str,
        stream: bool,
        debug: bool,
    ) -> Generator[AgentEvent, None, ChatCompletionMessage]:
        context_variables = defaultdict(str, context_variables)
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        messages = [{"role": "system", "content": instructions}] + history
        debug_print(debug, "Getting chat completion for...:", messages)

        yield AgentEvent(
            type=AgentEventType.AGENT_START,
            agent_name=agent.name,
            data={"currentTask": "Starting analysis"}
        )

        tools = [function_to_json(f) for f in agent.functions]
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop("context_variables", None)
            if "context_variables" in params["required"]:
                params["required"].remove("context_variables")

        yield AgentEvent(
            type=AgentEventType.AGENT_THINKING,
            agent_name=agent.name,
            data={"currentTask": "Processing request"}
        )

        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "tools": tools or None,
            "tool_choice": agent.tool_choice,
            "stream": stream,
            "json_mode": agent.json_mode,
            "json_schema": agent.json_schema,
        }

        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls

        yield AgentEvent(
            type=AgentEventType.AGENT_GENERATING,
            agent_name=agent.name,
            data={"currentTask": "Generating response"}
        )

        completion = self.client.chat.completions.create(**create_params)
        
        yield AgentEvent(
            type=AgentEventType.AGENT_GENERATED,
            agent_name=agent.name,
            data={"currentTask": "Response ready"}
        )

        return completion

    def handle_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: Dict,
        debug: bool,
        agent_name: str,
    ) -> Generator[AgentEvent, None, Response]:
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(
            messages=[], agent=None, context_variables={}
        )

        for tool_call in tool_calls:
            name = tool_call.function.name
            
            yield AgentEvent(
                type=AgentEventType.TOOL_CALL_START,
                agent_name=agent_name,
                data={
                    "currentTask": f"Executing tool: {name}",
                    "tool": name
                }
            )

            if name not in function_map:
                debug_print(debug, f"Tool {name} not found in function map.")
                partial_response.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "tool_name": name,
                        "content": f"Error: Tool {name} not found.",
                    }
                )
                continue

            args = json.loads(tool_call.function.arguments)
            debug_print(debug, f"Processing tool call: {name} with arguments {args}")

            func = function_map[name]
            if "context_variables" in func.__code__.co_varnames:
                args["context_variables"] = context_variables
            raw_result = function_map[name](**args)

            result: Result = self.handle_function_result(raw_result, debug)
            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "tool_name": name,
                    "content": result.value,
                }
            )
            
            yield AgentEvent(
                type=AgentEventType.TOOL_CALL_END,
                agent_name=agent_name,
                data={
                    "currentTask": f"Completed tool: {name}",
                    "tool": name,
                    "result": result.value
                }
            )

            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent
                yield AgentEvent(
                    type=AgentEventType.AGENT_HANDOFF,
                    agent_name=agent_name,
                    data={
                        "currentTask": "Handing off to new agent",
                        "nextAgent": result.agent.name
                    }
                )

        return partial_response

    def run(
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ) -> Generator[AgentEvent, None, Response]:
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns and active_agent:
            # Stream chat completion events
            completion = None
            for event in self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=False,
                debug=debug,
            ):
                if isinstance(event, AgentEvent):
                    yield event
                else:
                    completion = event

            message = completion.choices[0].message
            debug_print(debug, "Received completion:", message)
            message.sender = active_agent.name
            history.append(json.loads(message.model_dump_json()))

            if not message.tool_calls or not execute_tools:
                debug_print(debug, "Ending turn.")
                yield AgentEvent(
                    type=AgentEventType.AGENT_COMPLETE,
                    agent_name=active_agent.name,
                    data={
                        "currentTask": "Task completed",
                        "response": message.content
                    }
                )
                break

            # Handle function calls with event streaming
            partial_response = None
            for event in self.handle_tool_calls(
                message.tool_calls,
                active_agent.functions,
                context_variables,
                debug,
                active_agent.name
            ):
                if isinstance(event, AgentEvent):
                    yield event
                else:
                    partial_response = event

            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            if partial_response.agent:
                active_agent = partial_response.agent

        return Response(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
        )