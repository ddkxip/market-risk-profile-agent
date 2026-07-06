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

import re
from pathlib import Path

TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")

def validate_resolved_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if not TICKER_RE.fullmatch(ticker):
        raise ValueError("Unable to resolve input to a valid stock ticker")
    return ticker

def get_safe_cache_path(base_cache_dir: str, ticker: str, suffix: str) -> str:
    validated_ticker = validate_resolved_ticker(ticker)
    safe_key = validated_ticker.replace(".", "_").replace("-", "_").lower()
    
    # Resolve target directory and file path to absolute paths
    target_dir = Path(base_cache_dir).resolve()
    # Ensure directory exists
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = (target_dir / f"{safe_key}{suffix}").resolve()
    
    # Assert that the resolved path is strictly inside the target directory (path traversal check)
    if target_dir not in target_file.parents:
        raise ValueError("Path traversal attempt detected via ticker parameter")
        
    return str(target_file)

def generate_content_with_retry(client, model: str, contents, config=None, max_retries: int = 4, initial_delay: float = 2.0):
    import time
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            err_str = str(e).upper()
            is_transient = "429" in err_str or "LIMIT" in err_str or "EXHAUSTED" in err_str or "QUOTA" in err_str or "TEMPORARY" in err_str or "503" in err_str or "500" in err_str
            
            if is_transient and attempt < max_retries - 1:
                print(f"[Gemini API Retry] Attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                raise e


