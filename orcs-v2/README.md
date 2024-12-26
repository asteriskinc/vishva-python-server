Current Query to Task Completion Flow:

User Query → convert_query_to_task
    → Planner Agent breaks down query
    → get_dependencies enriches with dependencies
    → execute_task manages overall execution
        → execute_subtask for each subtask
            → run_agent_for_subtask handles agent execution