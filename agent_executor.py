"""
Pure API Module for executing Mistral AI Studio Agents.

This module acts as the modular "brick" the user requested.
It takes a query and an agent_id, calls the Mistral SDK,
intercepts the ToolCalls, executes the local database functions (from tools.py),
and returns the final agent response with automatic Rate Limit (429) retry backoff.
"""

import json
import time
from typing import Dict, Any

import config  # Ensures sys.path includes client-python
from mistralai.client import Mistral
from mistralai.client.models import ToolMessage, UserMessage, AssistantMessage
import tools

def execute_local_tool(tool_call) -> str:
    """Executes the mapped local tool and returns the JSON string result."""
    func_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments
    
    try:
        if func_name == "list_available_tables":
            return tools.list_available_tables()
        elif func_name == "get_table_columns":
            return tools.get_table_columns(args.get("table_name", ""))
        elif func_name == "get_entity_info":
            return tools.get_entity_info(args.get("entity_name", ""))
        elif func_name == "get_schema_metadata":
            return tools.get_schema_metadata(args.get("concept", ""))
        elif func_name == "lookup_qrt_coordinates":
            return tools.lookup_qrt_coordinates(args.get("table_name", ""), args.get("column_name", ""))
        elif func_name == "query_database":
            return tools.query_database(args.get("sql_query", ""))
        else:
            return json.dumps({"error": f"Unknown tool {func_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


class PureAgentExecutor:
    """Modular Execution Brick for Mistral AI Studio Agents."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is missing. Required for Agent API execution.")
        self.client = Mistral(api_key=self.api_key)

    def _call_agent_with_retry(self, agent_id: str, messages: list, max_retries: int = 4):
        """Calls client.agents.complete with exponential backoff on HTTP 429 Rate Limits."""
        for attempt in range(max_retries):
            try:
                return self.client.agents.complete(
                    agent_id=agent_id,
                    messages=messages
                )
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "rate" in err_str.lower()) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"⚠️ [Mistral API] Rate limit (429) atteint. Pause de {wait_time}s avant réessai ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise e

    def ask_agent(self, query: str, agent_id: str) -> Dict[str, Any]:
        """
        Executes the full conversational loop with the Mistral Agent.
        - Sends the user query.
        - While the Agent requests tools, executes them locally.
        - Returns the final response text.
        """
        messages = [{"role": "user", "content": query}]
        
        # Initial call to the Agent
        response = self._call_agent_with_retry(agent_id=agent_id, messages=messages)
        
        response_msg = response.choices[0].message
        messages.append(response_msg)
        
        execution_logs = []
        
        # Loop to handle Tool Calls
        while response_msg.tool_calls:
            tool_calls = response_msg.tool_calls
            for tcall in tool_calls:
                # Execute tool locally
                tool_result_str = execute_local_tool(tcall)
                execution_logs.append({
                    "tool": tcall.function.name,
                    "arguments": tcall.function.arguments,
                    "result": tool_result_str
                })
                
                # Append tool result to messages
                messages.append(ToolMessage(
                    tool_call_id=tcall.id,
                    name=tcall.function.name,
                    content=tool_result_str
                ))
                
            # Send results back to the Agent for the next reasoning step
            response = self._call_agent_with_retry(agent_id=agent_id, messages=messages)
            response_msg = response.choices[0].message
            messages.append(response_msg)
            
        return {
            "query": query,
            "agent_id": agent_id,
            "final_answer": response_msg.content,
            "tool_executions": execution_logs
        }

if __name__ == "__main__":
    # Example usage for CLI testing
    import sys
    if len(sys.argv) > 2:
        query = sys.argv[1]
        agent_id = sys.argv[2]
        executor = PureAgentExecutor()
        result = executor.ask_agent(query, agent_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python agent_executor.py '<query>' '<agent_id>'")
