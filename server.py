"""
FastAPI Server - Pure REST API for the ACPR Text-to-Data Agent.
No UI, No HTML. Exposes only API endpoints.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import config
from agent_executor import PureAgentExecutor

app = FastAPI(
    title="Mistral AI ACPR Pure Agent API",
    description="API modulaire pour exécuter l'Agent Studio sur des bases locales",
)

executor = None

def get_executor():
    global executor
    if executor is None:
        executor = PureAgentExecutor()
    return executor

class AgentQueryRequest(BaseModel):
    query: str
    agent_id: str

@app.post("/api/agent/ask")
def ask_agent_endpoint(req: AgentQueryRequest):
    """
    Main endpoint for the Agent API.
    Takes a query and the Mistral AI Studio agent_id.
    Executes the agent loop locally (tools) and returns the final answer.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="La requête ne peut pas être vide.")
    if not req.agent_id.strip():
        raise HTTPException(status_code=400, detail="L'agent_id est requis.")
        
    try:
        exec_engine = get_executor()
        result = exec_engine.ask_agent(req.query, req.agent_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
