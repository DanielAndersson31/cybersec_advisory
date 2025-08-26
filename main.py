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
@app.post("/api/chat")
async def chat_endpoint(request: Request):
    chat_request = await request.json()
    logger.info(f"Received chat request for thread {chat_request.get('thread_id')}")
    manager = request.app.state.conversation_manager
    if not manager or not manager.initialized:
        return {"error": "System not initialized"}, 503

    response = await manager.chat(message=chat_request.get("message"), thread_id=chat_request.get("thread_id"))
    return {"response": response}

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