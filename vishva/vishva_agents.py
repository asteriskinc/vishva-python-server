# vishva_agents.py is the class that allows to extend the functionality of the Orcs framework to vishva. 

from orcs.types import Agent

class AgentRegistry:
    """ Singleton class that registers all the agents in Vishva. """
    _instance = None 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.agents = Dict[str, Agent]
