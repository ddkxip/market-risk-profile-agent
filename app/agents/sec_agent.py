import urllib.request
import json
import re
from bs4 import BeautifulSoup
from google import genai
from app.config import get_gemini_client
from app.models import RiskProfile, RiskFactor

class SECAgent:
    def __init__(self):
        # SEC EDGAR requires a specific User-Agent format: CompanyName AdminContact@domain.com
        self.headers = {
            "User-Agent": "MarketRiskAgent/1.0 (ddkxi@gemini-capstone.com)"
        }

    def get_cik_from_ticker(self, ticker: str) -> str:
        """Resolves a ticker symbol to a 10-digit padded CIK number."""
        ticker = ticker.upper().strip()
        url = "https://www.sec.gov/files/company_tickers.json"
        
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            for company in data.values():
                if company['ticker'] == ticker:
                    return str(company['cik_str']).zfill(10)
        except Exception as e:
            print(f"Error fetching CIK map from SEC: {e}")
            
        # Common tickers hardcoded fallback to be robust
        fallbacks = {
            "AAPL": "0000320193",
            "MSFT": "0000789019",
            "GOOG": "0001652044",
            "GOOGL": "0001652044",
            "AMZN": "0001018724",
            "META": "0001326801",
            "TSLA": "0001318605",
            "NVDA": "0001045810"
        }
        return fallbacks.get(ticker, None)

    def fetch_recent_filing_url(self, cik: str) -> tuple[str, str, str]:
        """Fetches the latest 10-K filing URL and metadata."""
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        req = urllib.request.Request(url, headers=self.headers)
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        recent_filings = data['filings']['recent']
        
        # Look for the most recent 10-K
        idx = -1
        for i, form in enumerate(recent_filings['form']):
            if form == '10-K':
                idx = i
                break
                
        # If no 10-K found, try 10-Q
        if idx == -1:
            for i, form in enumerate(recent_filings['form']):
                if form == '10-Q':
                    idx = i
                    break
                    
        if idx == -1:
            raise ValueError(f"No 10-K or 10-Q filings found for CIK {cik}")
            
        accession = recent_filings['accessionNumber'][idx]
        primary_doc = recent_filings['primaryDocument'][idx]
        filing_date = recent_filings['filingDate'][idx]
        form_type = recent_filings['form'][idx]
        
        # Format accession number without hyphens for the archive URL
        accession_no_hyphen = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_hyphen}/{primary_doc}"
        
        return filing_url, form_type, filing_date

    def extract_risk_factors_text(self, url: str) -> str:
        """Downloads filing HTML, extracts text, and attempts to find Item 1A (Risk Factors)."""
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get all text
        text = soup.get_text(separator=' ')
        
        # Clean text
        text = re.sub(r'\s+', ' ', text)
        
        # Try to find "Item 1A. Risk Factors" or "Item 1A Risk Factors"
        match = re.search(r'item\s+1a\.?\s+risk\s+factors', text, re.IGNORECASE)
        if not match:
            # Try a broader search
            match = re.search(r'risk\s+factors', text, re.IGNORECASE)
            
        if match:
            start_idx = match.start()
            # Extract up to 60,000 characters from the match start to avoid hitting LLM limits or reading the entire 10-K
            return text[start_idx:start_idx + 60000]
            
        # Return first 60,000 characters if we can't find the keyword (highly unlikely but safe fallback)
        return text[:60000]

    def analyze_risk_with_gemini(self, ticker: str, text: str, form_type: str, filing_date: str) -> RiskProfile:
        """Sends extracted text to Gemini to parse into structured RiskProfile."""
        client = get_gemini_client()
        
        prompt = f"""
        You are an expert financial analyst. Analyze the following text extracted from {ticker}'s {form_type} SEC filing filed on {filing_date}.
        Extract the core corporate risk factors mentioned in the filing.
        Summarize the risks, categorize them, evaluate their severity (Low, Medium, High), and provide an overall risk rating.
        
        Filing Text:
        ---
        {text}
        ---
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': RiskProfile,
                'temperature': 0.1
            }
        )
        
        # parse json from response
        return RiskProfile.model_validate_json(response.text)

    def analyze_company_risks_fallback(self, ticker: str) -> RiskProfile:
        """Fallback method that uses Gemini's internal knowledge of a company's risks if SEC fetching fails."""
        client = get_gemini_client()
        
        prompt = f"""
        You are an expert financial analyst. Provide a detailed risk profile for {ticker} based on your internal knowledge of the company's recent SEC filings, competitive landscape, regulatory exposures, and operational challenges.
        Make sure the rating and risk factors are up-to-date as of 2026.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': RiskProfile,
                'temperature': 0.2
            }
        )
        
        return RiskProfile.model_validate_json(response.text)

    def get_risk_profile(self, ticker: str) -> RiskProfile:
        """Main entry point to retrieve risk profile."""
        import os
        
        # Resolve cache path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_dir = os.path.join(base_dir, ".cache", "sec")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{ticker.lower()}_profile.json")
        
        # Try loading from cache
        if os.path.exists(cache_file):
            try:
                print(f"[{ticker}] Loading SEC risk profile from local cache...")
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                profile = RiskProfile.model_validate(cached_data)
                
                # If cached profile doesn't have filing_url, resolve and add it
                if not profile.filing_url:
                    cik = self.get_cik_from_ticker(ticker)
                    if cik:
                        profile.filing_url = f"https://www.sec.gov/edgar/browse/?CIK={cik}"
                        # Save updated profile with url back to cache
                        with open(cache_file, "w") as f_out:
                            json.dump(profile.model_dump(), f_out, indent=2)
                return profile
            except Exception as ce:
                print(f"[{ticker}] Failed to load SEC cache: {ce}")

        # If not cached, fetch and compute
        profile = None
        try:
            cik = self.get_cik_from_ticker(ticker)
            if not cik:
                raise ValueError(f"Could not resolve CIK for ticker {ticker}")
                
            filing_url, form_type, filing_date = self.fetch_recent_filing_url(cik)
            print(f"Fetching SEC filing for {ticker} from {filing_url}...")
            
            raw_text = self.extract_risk_factors_text(filing_url)
            profile = self.analyze_risk_with_gemini(ticker, raw_text, form_type, filing_date)
            profile.filing_url = filing_url
            
        except Exception as e:
            print(f"SEC direct fetch failed for {ticker} ({e}). Falling back to Gemini knowledge base...")
            profile = self.analyze_company_risks_fallback(ticker)
            # Add fallback search link
            cik = self.get_cik_from_ticker(ticker)
            if cik:
                profile.filing_url = f"https://www.sec.gov/edgar/browse/?CIK={cik}"
            else:
                profile.filing_url = f"https://www.sec.gov/edgar/searchedgar/companysearch"

        # Write to cache if profile was obtained
        if profile:
            try:
                with open(cache_file, "w") as f:
                    json.dump(profile.model_dump(), f, indent=2)
            except Exception as ce:
                print(f"[{ticker}] Failed to write SEC cache: {ce}")

        return profile
