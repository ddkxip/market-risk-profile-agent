import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sys
import os

from app.models import (
    AnalysisRequest, 
    CompanyProfileResponse, 
    ComparisonRequest, 
    ComparisonResponse,
    ChatRequest
)
from app.agents.coordinator import CoordinatorAgent
from app.agents.comparison_agent import ComparisonAgent
from app.config import get_gemini_client
from app.session_store import SessionStore

app = FastAPI(
    title="Market Risk & Trading Profile API",
    description="ADK-powered multi-agent system synthesizing corporate risk and trading profiles with chat memory.",
    version="1.0.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve static directory relative to this file
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# Initialize Coordinator and Comparison Agents
coordinator = CoordinatorAgent()
comparison_agent = ComparisonAgent()

# Profile Generation Endpoint
@app.post("/api/analyze", response_model=CompanyProfileResponse)
async def analyze_company(request: AnalysisRequest):
    try:
        # Validate that client can be initialized
        get_gemini_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini credentials verification failed: {str(e)}"
        )
        
    try:
        profile = await coordinator.generate_profile_async(
            ticker=request.ticker,
            session_id=request.session_id
        )
        return profile
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while compiling the profile: {str(e)}"
        )

# Chatbot Copilot Endpoint
@app.post("/api/chat")
async def chat_copilot(request: ChatRequest):
    try:
        get_gemini_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini credentials verification failed: {str(e)}"
        )
        
    try:
        reply = await coordinator.chat_async(
            message=request.message,
            session_id=request.session_id
        )
        return {"reply": reply}
    except Exception as e:
        print(f"Error during chat: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during the conversation: {str(e)}"
        )

# Chat Session History Retrieve Endpoint
@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    try:
        db = SessionStore()
        history = db.get_history(session_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )

# Clear Session Endpoint
@app.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    try:
        db = SessionStore()
        db.clear_history(session_id)
        return {"status": "success", "message": f"Session {session_id} history cleared."}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear session history: {str(e)}"
        )

@app.post("/api/compare", response_model=ComparisonResponse)
async def compare_companies(request: ComparisonRequest):
    try:
        get_gemini_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini credentials verification failed: {str(e)}"
        )
    try:
        comparison = await comparison_agent.compare_companies_async(
            ticker_a=request.ticker_a,
            ticker_b=request.ticker_b
        )
        return comparison
    except Exception as e:
        print(f"Error during comparison: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while compiling the comparison: {str(e)}"
        )

# Serve Frontend Static Files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
