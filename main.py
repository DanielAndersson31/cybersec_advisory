import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

from config.settings import settings
from conversation.manager import ConversationManager
from utils.logging import setup_logging
from workflow.graph import CybersecurityTeamGraph
from workflow.schemas import ChatResponse

# --- Setup ---
load_dotenv() # Load environment variables from .env file
setup_logging()
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str

# --- Global State & Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("🚀 Initializing Cybersecurity Advisory System for API...")
    workflow = CybersecurityTeamGraph()
    llm_client = ChatOpenAI(model=settings.default_model, temperature=0.1, max_tokens=4000)
    app.state.conversation_manager = ConversationManager(workflow=workflow, llm_client=llm_client)
    await app.state.conversation_manager.initialize()
    logger.info("✅ System initialized successfully for API.")
    yield
    # --- Shutdown logic would go here ---
    logger.info("🛑 Shutting down application.")

app = FastAPI(lifespan=lifespan)

# --- API Endpoints ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request):
    try:
        chat_request = await request.json()
        logger.info(f"Received chat request for thread {chat_request.get('thread_id')}")
        manager = request.app.state.conversation_manager
        if not manager or not manager.initialized:
            return {"error": "System not initialized"}, 503

        final_state = await manager.chat(message=chat_request.get("message"), thread_id=chat_request.get("thread_id"))
        
        logger.info(f"Final state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'Not a dict'}")
        
        response_data = {
            "response": final_state.get("final_answer"),
            "agent_name": None,
            "agent_role": None,
            "tools_used": []
        }

        # Extract agent details and tool usage based on response type
        team_responses = final_state.get("team_responses", [])
        
        if len(team_responses) > 1:
            # Multi-agent team response - show "Advisory Team"
            response_data["agent_name"] = "Advisory Team"
            response_data["agent_role"] = "team"
            all_tools = []
            for resp in team_responses:
                if resp.tools_used:
                    all_tools.extend([tool.tool_name for tool in resp.tools_used])
            response_data["tools_used"] = sorted(list(set(all_tools)))
            
        elif len(team_responses) == 1:
            # Single agent response - show individual agent name
            first_responder = team_responses[0]
            response_data["agent_name"] = first_responder.agent_name
            response_data["agent_role"] = first_responder.agent_role.value
            if first_responder.tools_used:
                response_data["tools_used"] = [tool.tool_name for tool in first_responder.tools_used]
                
        elif final_state.get("response_strategy") == "general_query":
            # General assistant response
            response_data["agent_name"] = "General Assistant"
            response_data["agent_role"] = "general"
            # Check if web search was used (common for general queries)
            if "web_search" in str(final_state.get("final_answer", "")).lower():
                response_data["tools_used"] = ["web_search"]
                
        else:
            # Fallback for any other response type
            response_data["agent_name"] = "Cybersecurity Assistant"
            response_data["agent_role"] = "assistant"

        logger.info(f"Returning response: {response_data}")
        logger.info(f"Team responses count: {len(team_responses)}")
        if team_responses:
            logger.info(f"Agent names: {[resp.agent_name for resp in team_responses]}")
            logger.info(f"Agent roles: {[resp.agent_role.value for resp in team_responses]}")
        return ChatResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return ChatResponse(
            response="I apologize, but I encountered an error processing your request. Please try again.",
            agent_name="System",
            agent_role="error",
            tools_used=[]
        )

# --- Static File Serving ---
frontend_dir = Path(__file__).resolve().parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    file_path = frontend_dir / (full_path or "index.html")
    if file_path.is_dir():
        file_path = file_path / "index.html"
    
    if file_path.exists():
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
        
    return HTMLResponse("Frontend not found", status_code=404)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)