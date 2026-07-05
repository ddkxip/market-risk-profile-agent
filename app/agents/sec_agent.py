import urllib.request
import json
import re
import os
import time
from bs4 import BeautifulSoup
from google import genai
from app.config import get_gemini_client
from app.models import RiskProfile, RiskFactor

def load_sec_tickers(headers: dict) -> dict:
    """Loads the SEC company tickers mapping, utilizing a local file cache (expires in 24h)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_dir = os.path.join(base_dir, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "company_tickers.json")

    # Cache duration: 24 hours (86400 seconds)
    if os.path.exists(cache_file):
        try:
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime < 86400:
                with open(cache_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error reading cached company_tickers.json: {e}")

    # Not cached or expired -> fetch from SEC
    url = "https://www.sec.gov/files/company_tickers.json"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        # Save to cache
        try:
            with open(cache_file, "w") as f:
                json.dump(data, f)
        except Exception as ce:
            print(f"Failed to write company_tickers.json cache: {ce}")
        return data
    except Exception as e:
        print(f"Error fetching tickers from SEC: {e}")
        # Return fallback from cache if available
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

class SECAgent:
    def __init__(self):
        # SEC EDGAR requires a specific User-Agent format: CompanyName AdminContact@domain.com
        self.headers = {
            "User-Agent": "MarketRiskAgent/1.0 (ddkxi@gemini-capstone.com)"
        }

    def get_cik_from_ticker(self, ticker: str) -> str:
        """Resolves a ticker symbol to a 10-digit padded CIK number."""
        ticker = ticker.upper().strip()
        
        data = load_sec_tickers(self.headers)
        for company in data.values():
            if company['ticker'] == ticker:
                return str(company['cik_str']).zfill(10)
            
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
        matches = list(re.finditer(r'item\s+1a\.?\s+risk\s+factors', text, re.IGNORECASE))
        if not matches:
            # Try a broader search
            matches = list(re.finditer(r'risk\s+factors', text, re.IGNORECASE))
            
        # ToC skipping: ignore matches in the first 8000 characters
        substantive_match = None
        for m in matches:
            if m.start() > 8000:
                substantive_match = m
                break
        if not substantive_match and matches:
            substantive_match = matches[-1]
            
        if substantive_match:
            start_idx = substantive_match.start()
            # Find the next item to bound the text copy (e.g. Item 1B, Item 2)
            end_match = re.search(r'item\s+(1b|2)\b', text[start_idx:], re.IGNORECASE)
            if end_match:
                end_idx = start_idx + end_match.start()
                section_text = text[start_idx:end_idx].strip()
                return section_text[:60000]
            else:
                return text[start_idx:start_idx + 60000]
            
        return text[:60000]

    def analyze_risk_with_gemini(self, ticker: str, k_text: str, k_date: str, q_text: str, q_date: str) -> RiskProfile:
        """Sends extracted 10-K and/or 10-Q text to Gemini to parse into structured RiskProfile."""
        client = get_gemini_client()
        
        filing_details_str = ""
        filing_contents_str = ""
        
        if k_text:
            filing_details_str += f"10-K filed on {k_date}"
            filing_contents_str += f"""
            --- ANNUAL 10-K RISK FACTORS (Filed: {k_date}) ---
            <sec_10k_risk_text>
            {k_text}
            </sec_10k_risk_text>
            """
            
        if q_text:
            if filing_details_str:
                filing_details_str += " and "
            filing_details_str += f"10-Q filed on {q_date}"
            filing_contents_str += f"""
            --- QUARTERLY 10-Q RISK UPDATES (Filed: {q_date}) ---
            <sec_10q_risk_text>
            {q_text}
            </sec_10q_risk_text>
            """
            
        if not filing_contents_str:
            raise ValueError(f"No risk text content available for Gemini analysis on {ticker}")
            
        prompt = f"""
        You are an expert financial analyst. Analyze the following corporate risk information for {ticker} extracted from its recent SEC filings ({filing_details_str}).
        Evaluate both the broad annual structural risks (from the 10-K) and any recent quarterly updates or material developments (from the 10-Q).
        
        Filing Texts:
        {filing_contents_str}
        
        Summarize the risks, categorize them, evaluate their severity (Low, Medium, High), and provide an overall risk rating.
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
        
        profile = RiskProfile.model_validate_json(response.text)
        # Prepend ungrounded warning notice for Responsible AI
        profile.summary = f"[Note: SEC EDGAR direct filing fetch failed. The following risks are synthesized from Gemini's internal market knowledge rather than direct filing extracts.] {profile.summary}"
        return profile

    def get_risk_profile(self, ticker: str) -> RiskProfile:
        """Main entry point to retrieve risk profile."""
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
                
                if not profile.filing_url:
                    cik = self.get_cik_from_ticker(ticker)
                    if cik:
                        profile.filing_url = f"https://www.sec.gov/edgar/browse/?CIK={cik}"
                        with open(cache_file, "w") as f_out:
                            json.dump(profile.model_dump(), f_out, indent=2)
                return profile
            except Exception as ce:
                print(f"[{ticker}] Failed to load SEC cache: {ce}")

        # If not cached, fetch and compute
        try:
            cik = self.get_cik_from_ticker(ticker)
            if not cik:
                raise ValueError(f"Could not resolve CIK for ticker {ticker}")
                
            # Fetch CIK submissions JSON
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            recent_filings = data['filings']['recent']
            
            # Find the most recent 10-K and 10-Q indices
            idx_k = -1
            idx_q = -1
            for i, form in enumerate(recent_filings['form']):
                if form == '10-K' and idx_k == -1:
                    idx_k = i
                elif form == '10-Q' and idx_q == -1:
                    idx_q = i
                if idx_k != -1 and idx_q != -1:
                    break
                    
            if idx_k == -1 and idx_q == -1:
                raise ValueError(f"No 10-K or 10-Q filings found for CIK {cik}")
                
            # Helper to generate filing details
            def get_filing_details(idx: int) -> tuple[str, str, str]:
                accession = recent_filings['accessionNumber'][idx]
                primary_doc = recent_filings['primaryDocument'][idx]
                f_date = recent_filings['filingDate'][idx]
                f_type = recent_filings['form'][idx]
                accession_no_hyphen = accession.replace("-", "")
                f_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_hyphen}/{primary_doc}"
                return f_url, f_type, f_date

            k_url, k_text, k_date = None, None, None
            q_url, q_text, q_date = None, None, None
            
            if idx_k != -1:
                k_url, _, k_date = get_filing_details(idx_k)
                print(f"[{ticker}] Extracting 10-K filing from {k_url}...")
                k_text = self.extract_risk_factors_text(k_url)
                
            if idx_q != -1:
                q_url, _, q_date = get_filing_details(idx_q)
                print(f"[{ticker}] Extracting 10-Q filing from {q_url}...")
                q_text = self.extract_risk_factors_text(q_url)
                
            profile = self.analyze_risk_with_gemini(ticker, k_text, k_date, q_text, q_date)
            profile.filing_url = q_url if q_url else k_url
            
        except Exception as e:
            print(f"SEC direct fetch failed for {ticker} ({e}).")
            raise ValueError(f"Failed to retrieve or parse SEC filing risk factors for {ticker}: {str(e)}")

        # Write to cache if profile was obtained
        if profile:
            try:
                with open(cache_file, "w") as f:
                    json.dump(profile.model_dump(), f, indent=2)
            except Exception as ce:
                print(f"[{ticker}] Failed to write SEC cache: {ce}")

        return profile
