# Current Query to Task Completion Lifecycle

0. Client sends a query to the server through a web socket. 
1. Server asks ORCS to convert the raw user query into a Task Object. (Planner Agent is response for this)
2. Task Object contains SubTask Objects as well. 
3. Task (and its SubTasks) are then executed by the agents. 
4. Results are stored back into the SubTask objects (for subtask results) and Task Object (for task results).
5. Server will then convert the results into the desired format and returns it to the client side through the web socket. 