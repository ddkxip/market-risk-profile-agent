import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.models import AnalysisRequest, CompanyProfileResponse
from app.agents.coordinator import CoordinatorAgent
from app.config import GEMINI_API_KEY
import sys
import os

app = FastAPI(
    title="Market Risk & Trading Profile API",
    description="Multi-agent system synthesizing corporate risk and trading profiles using Gemini and yfinance.",
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

# Initialize Coordinator
coordinator = CoordinatorAgent()

# API Endpoint
@app.post("/api/analyze", response_model=CompanyProfileResponse)
async def analyze_company(request: AnalysisRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not set on the server. Please add it to your configuration."
        )
        
    try:
        profile = coordinator.generate_profile(
            ticker=request.ticker,
            custom_company_name=request.company_name
        )
        return profile
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while compiling the profile: {str(e)}"
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
