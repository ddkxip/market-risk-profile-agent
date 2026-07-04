import os
from dotenv import load_dotenv
from google import genai

# Load .env file if it exists
load_dotenv()

# Configuration settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")

# Initialize Gemini Client if key is present
def get_gemini_client():
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please set it in your environment or in a .env file."
        )
    return genai.Client(api_key=GEMINI_API_KEY)
