import asyncio
import websockets
import json
from datetime import datetime
from typing import Dict, Any
import colorama
from colorama import Fore, Style
import sys
import aioconsole  # You might need to: pip install aioconsole

# Initialize colorama for cross-platform colored output
colorama.init()

class AgentStreamViewer:
    def __init__(self):
        self.current_agent = None
        self.current_content = ""
        self.conversation_in_progress = False
        
    def print_agent_header(self, agent_name: str):
        print(f"\n{Fore.CYAN}{'='*20} {agent_name} {'='*20}{Style.RESET_ALL}")
        
    def print_tool_call(self, agent: str, tool: str, args: Dict[str, Any]):
        print(f"{Fore.YELLOW}[{agent}] Calling: {tool}{Style.RESET_ALL}")
        # print(f"{Fore.YELLOW}Arguments: {json.dumps(args, indent=2)}{Style.RESET_ALL}")
        
    def print_content(self, agent: str, content: str):
        if agent != self.current_agent:
            print(f"\n{Fore.GREEN}{agent}:{Style.RESET_ALL}", end=" ")
            self.current_agent = agent
        print(content, end="", flush=True)
        self.current_content += content
        
    def handle_event(self, event: Dict[str, Any]):
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            if 'timestamp' in event:
                timestamp = datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')
            
            match event['type']:
                case 'agent_start':
                    self.conversation_in_progress = True
                    self.print_agent_header(event['agent'])
                    message = event.get('data', {}).get('message', 'Started processing')
                    print(f"{Fore.BLUE}[{timestamp}] {message}{Style.RESET_ALL}")
                    
                case 'agent_switch':
                    previous = event.get('data', {}).get('previous_agent', 'previous agent')
                    print(f"\n{Fore.MAGENTA}[{timestamp}] Switching from {previous} to {event['agent']}{Style.RESET_ALL}")
                    
                case 'content':
                    content = event.get('data', {}).get('content', '')
                    if content:
                        self.print_content(event['agent'], content)
                    
                case 'tool_call':
                    print()  # New line for better formatting
                    tool_data = event.get('data', {})
                    self.print_tool_call(
                        event['agent'],
                        tool_data.get('tool', 'unknown_tool'),
                        tool_data.get('arguments', {})
                    )
                    
                case 'agent_complete':
                    if self.current_content:
                        print()  # New line after content
                    self.current_content = ""
                    print(f"\n{Fore.GREEN}[{timestamp}] {event['agent']} completed their task{Style.RESET_ALL}")
                    
                case 'conversation_complete':
                    print(f"\n{Fore.BLUE}[{timestamp}] Conversation completed{Style.RESET_ALL}")
                    final_agent = event.get('data', {}).get('final_agent')
                    if final_agent:
                        print(f"{Fore.BLUE}Final agent: {final_agent}{Style.RESET_ALL}")
                    self.conversation_in_progress = False
                    print(f"\n{Fore.CYAN}Ready for next query...{Style.RESET_ALL}")
                    
                case 'error':
                    error_msg = event.get('data', {}).get('message', 'Unknown error occurred')
                    print(f"\n{Fore.RED}[{timestamp}] Error: {error_msg}{Style.RESET_ALL}")
                    self.conversation_in_progress = False
                    print(f"\n{Fore.CYAN}Ready for next query...{Style.RESET_ALL}")
                
                case _:
                    print(f"\n{Fore.YELLOW}[{timestamp}] Unknown event type: {event['type']}{Style.RESET_ALL}")
        
        except Exception as e:
            print(f"{Fore.RED}Error handling event: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.RED}Event data: {json.dumps(event, indent=2)}{Style.RESET_ALL}")
            self.conversation_in_progress = False

async def interactive_session():
    uri = "ws://localhost:8000/ws"
    viewer = AgentStreamViewer()
    
    print(f"{Fore.CYAN}Starting ORCS Interactive Session{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Type 'exit' to quit{Style.RESET_ALL}\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            while True:
                if not viewer.conversation_in_progress:
                    # Use aioconsole to get input asynchronously
                    query = await aioconsole.ainput(f"{Fore.CYAN}Enter your query: {Style.RESET_ALL}")
                    
                    if query.lower() in ['exit', 'quit', 'q']:
                        print(f"\n{Fore.YELLOW}Ending session...{Style.RESET_ALL}")
                        break
                    
                    if not query.strip():
                        continue
                    
                    # Send search query
                    message = {
                        "action": "start_search",
                        "query": query
                    }
                    await websocket.send(json.dumps(message))
                
                try:
                    response = await websocket.recv()
                    event = json.loads(response)
                    viewer.handle_event(event)
                    
                except websockets.exceptions.ConnectionClosed:
                    print(f"\n{Fore.RED}Connection closed by server{Style.RESET_ALL}")
                    break
                    
    except ConnectionRefusedError:
        print(f"{Fore.RED}Connection refused. Make sure the WebSocket server is running.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        asyncio.run(interactive_session())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Session terminated by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Session ended due to error: {str(e)}{Style.RESET_ALL}")