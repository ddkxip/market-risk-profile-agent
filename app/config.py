import os
from dotenv import load_dotenv
from google import genai

# Load .env file if it exists
load_dotenv()

# Configuration settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")

# Vertex AI settings
USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1", "yes") or \
               os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in ("true", "1", "yes")
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

# Initialize Gemini Client
def get_gemini_client():
    # Treat placeholder value as unset
    has_api_key = GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY != "your_gemini_api_key_here"
    
    if has_api_key:
        return genai.Client(api_key=GEMINI_API_KEY)
    
    # If API key is not present, check if Vertex AI / ADC is enabled or we have GCP configuration
    if USE_VERTEXAI or GCP_PROJECT or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        client_kwargs = {"vertexai": True}
        if GCP_PROJECT:
            client_kwargs["project"] = GCP_PROJECT
        if GCP_LOCATION:
            client_kwargs["location"] = GCP_LOCATION
        return genai.Client(**client_kwargs)
        
    raise ValueError(
        "No Gemini credentials found. Please set GEMINI_API_KEY in your environment or .env file, "
        "or configure Google Cloud Application Default Credentials (ADC) by setting GOOGLE_APPLICATION_CREDENTIALS "
        "or running 'gcloud auth application-default login' and setting GOOGLE_GENAI_USE_VERTEXAI=true."
    )

