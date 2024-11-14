import asyncio
import websockets
import json
from datetime import datetime
from typing import Dict, Any
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform colored output
colorama.init()

class AgentStreamViewer:
    def __init__(self):
        self.current_agent = None
        self.current_content = ""
        
    def print_agent_header(self, agent_name: str):
        print(f"\n{Fore.CYAN}{'='*20} {agent_name} {'='*20}{Style.RESET_ALL}")
        
    def print_tool_call(self, agent: str, tool: str, args: Dict[str, Any]):
        print(f"{Fore.YELLOW}[{agent}] Calling: {tool}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Arguments: {json.dumps(args, indent=2)}{Style.RESET_ALL}")
        
    def print_content(self, agent: str, content: str):
        if agent != self.current_agent:
            print(f"\n{Fore.GREEN}{agent}:{Style.RESET_ALL}", end=" ")
            self.current_agent = agent
        print(content, end="", flush=True)
        self.current_content += content
        
    def handle_event(self, event: Dict[str, Any]):
        try:
            # Get current timestamp if not provided in event
            timestamp = datetime.now().strftime('%H:%M:%S')
            if 'timestamp' in event:
                timestamp = datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')
            
            match event['type']:
                case 'agent_start':
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
                    
                case 'error':
                    error_msg = event.get('data', {}).get('message', 'Unknown error occurred')
                    print(f"\n{Fore.RED}[{timestamp}] Error: {error_msg}{Style.RESET_ALL}")
                
                case _:
                    print(f"\n{Fore.YELLOW}[{timestamp}] Unknown event type: {event['type']}{Style.RESET_ALL}")
        
        except Exception as e:
            print(f"{Fore.RED}Error handling event: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.RED}Event data: {json.dumps(event, indent=2)}{Style.RESET_ALL}")

async def test_search_query(query: str):
    uri = "ws://localhost:8000/ws"
    viewer = AgentStreamViewer()
    
    print(f"\n{Fore.CYAN}Testing search query: {query}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            # Send search query
            message = {
                "action": "start_search",
                "query": query
            }
            await websocket.send(json.dumps(message))
            
            # Listen for responses
            while True:
                try:
                    response = await websocket.recv()
                    event = json.loads(response)
                    viewer.handle_event(event)
                    
                except websockets.exceptions.ConnectionClosed:
                    print(f"\n{Fore.RED}Connection closed by server{Style.RESET_ALL}")
                    break
                except Exception as e:
                    print(f"\n{Fore.RED}Error processing message: {str(e)}{Style.RESET_ALL}")
                    break
                    
    except ConnectionRefusedError:
        print(f"{Fore.RED}Connection refused. Make sure the WebSocket server is running.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

async def run_tests():
    # Test queries that should trigger different agent pathways
    test_queries = [
        "where can I watch Smile 2?",  # Should trigger movie agent
        "what's the weather like in Venice beach?",  # Should trigger web agent
        "how do I get to Santa Monica pier?",  # Should trigger directions agent
        "what are my interests?",  # Should trigger personal context agent
    ]
    
    for query in test_queries:
        await test_search_query(query)
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
        await asyncio.sleep(2)  # Pause between tests

if __name__ == "__main__":
    print(f"{Fore.CYAN}Starting ORCS WebSocket Client Tests{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    
    # Run single test
    asyncio.run(test_search_query("where can I watch Smile 2?"))
    
    # Run multiple tests
    # asyncio.run(run_tests())