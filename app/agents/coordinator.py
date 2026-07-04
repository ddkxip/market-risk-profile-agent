from datetime import datetime
import yfinance as yf
from google import genai
from pydantic import BaseModel, Field
from app.config import get_gemini_client
from app.models import CompanyProfileResponse, Projections
from app.agents.market_data_agent import MarketDataAgent
from app.agents.sec_agent import SECAgent
from app.agents.news_agent import NewsAgent
from app.agents.macro_agent import MacroAgent

class SynthesizedFields(BaseModel):
    overall_summary: str = Field(..., description="High-level investor summary")
    projections: Projections = Field(..., description="Short-term and long-term outlooks")

class CoordinatorAgent:
    def __init__(self):
        self.market_agent = MarketDataAgent()
        self.sec_agent = SECAgent()
        self.news_agent = NewsAgent()
        self.macro_agent = MacroAgent()

    def get_company_name(self, ticker: str) -> str:
        """Retrieves the full company name using yfinance."""
        try:
            stock = yf.Ticker(ticker)
            return stock.info.get("longName", ticker)
        except Exception:
            return ticker

    def resolve_ticker(self, query: str) -> str:
        """Attempts to resolve a company name query to a valid ticker using SEC tickers database."""
        query_clean = query.upper().strip()
        if not query_clean:
            return query
            
        # If it looks like a standard ticker (1-5 alphabetical characters), use it directly
        if query_clean.isalpha() and 1 <= len(query_clean) <= 5:
            return query_clean
            
        try:
            import urllib.request
            import json
            
            headers = {"User-Agent": "MarketRiskAgent/1.0 (ddkxi@gemini-capstone.com)"}
            url = "https://www.sec.gov/files/company_tickers.json"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            for company in data.values():
                title = company.get('title', '').upper()
                ticker_symbol = company.get('ticker', '').upper()
                
                # Check for substring match (e.g. "APPLE" matches "APPLE INC")
                if query_clean in title or title in query_clean:
                    print(f"[Resolver] Resolved '{query}' to ticker '{ticker_symbol}'")
                    return ticker_symbol
        except Exception as e:
            print(f"Error in ticker resolver: {e}")
            
        return query_clean

    def generate_profile(self, ticker: str, custom_company_name: str = None) -> CompanyProfileResponse:
        ticker = self.resolve_ticker(ticker)
        
        import os
        import json
        import time
        
        # Resolve cache path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_dir = os.path.join(base_dir, ".cache", "profiles")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{ticker.lower()}_profile.json")
        
        # Cache duration: 2 hours (7200 seconds)
        if os.path.exists(cache_file):
            try:
                mtime = os.path.getmtime(cache_file)
                if time.time() - mtime < 7200:
                    print(f"[{ticker}] Loading FULL company profile from cache...")
                    with open(cache_file, "r") as f:
                        cached_data = json.load(f)
                    return CompanyProfileResponse.model_validate(cached_data)
                else:
                    print(f"[{ticker}] Cached profile expired, re-generating...")
            except Exception as ce:
                print(f"[{ticker}] Failed to load cached profile: {ce}")

        print(f"[{ticker}] Starting profile synthesis...")

        # 1. Gather all sub-agent data
        # Technical indicators
        tech_data, historical_data = self.market_agent.get_indicators(ticker)
        print(f"[{ticker}] Market technicals retrieved.")

        # SEC risk profile
        sec_data = self.sec_agent.get_risk_profile(ticker)
        print(f"[{ticker}] SEC risks analyzed.")

        # News & Sentiment analysis
        sentiment_data = self.news_agent.get_sentiment(ticker)
        print(f"[{ticker}] News sentiment evaluated.")

        # Macroeconomic factors
        macro_data = self.macro_agent.get_macro_factors(ticker)
        print(f"[{ticker}] Macroeconomic impacts analyzed.")

        # Resolve Company Name
        company_name = custom_company_name or self.get_company_name(ticker)

        # 2. Synthesize results using Gemini
        client = get_gemini_client()
        
        # Prepare context for the final LLM synthesis
        context_str = f"""
        Company: {company_name} ({ticker})
        Date: {datetime.now().strftime('%Y-%m-%d')}
        
        --- TECHNICAL TRENDS ---
        Current Price: ${tech_data.current_price}
        RSI (14): {tech_data.rsi_14} ({tech_data.rsi_status})
        MACD: {tech_data.macd_value} (Signal: {tech_data.macd_signal}, Status: {tech_data.macd_status})
        SMA 50: ${tech_data.sma_50}
        SMA 200: ${tech_data.sma_200}
        Trend: {tech_data.trend_status}
        
        --- SEC FILING RISKS ---
        Overall SEC Risk Rating: {sec_data.overall_rating}
        SEC Risk Summary: {sec_data.summary}
        Key SEC Risk Factors:
        """
        for factor in sec_data.factors:
            context_str += f"\n- [{factor.category} | Severity: {factor.severity}] {factor.description}"
            
        context_str += f"""
        
        --- NEWS & SENTIMENT ---
        Overall Sentiment: {sentiment_data.overall_sentiment} (Score: {sentiment_data.score})
        Key news takeaways:
        """
        for item in sentiment_data.items:
            context_str += f"\n- {item.headline} (Sentiment: {item.sentiment}) Takeaway: {item.takeaway}"
            
        context_str += f"""
        
        --- MACROECONOMIC FACTORS ---
        """
        for factor in macro_data:
            context_str += f"\n- [{factor.factor_name} | Impact: {factor.impact_level}] {factor.description}"

        prompt = f"""
        You are the Chief Investment Officer. Synthesize the following multi-dimensional dataset for {company_name} ({ticker}) into an overall investor summary and short-to-long-term projections.
        
        Company Analysis Data:
        {context_str}
        
        Write:
        1. An overall_summary (a paragraph of ~100-150 words summarizing the investment case, balancing the technical, sentiment, micro-risk, and macro-risk dimensions).
        2. Projections:
           - short_term: Short-term projection (1-3 months) detailing how technical momentum, news catalysts, and macro issues will combine to drive the stock.
           - long_term: Long-term projection (12+ months) detailing how the fundamental SEC risks, competitive advantages, and macroeconomic environment will shape the company's valuation.
        """

        # We request Gemini to return the synthesized part conforming to our schema.
        # Since we want to return a complete CompanyProfileResponse, we will populate the sub-fields using our already calculated objects.

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': SynthesizedFields,
                'temperature': 0.3
            }
        )
        
        synthesis = SynthesizedFields.model_validate_json(response.text)

        # 3. Assemble and return the full response
        profile = CompanyProfileResponse(
            ticker=ticker,
            company_name=company_name,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            overall_summary=synthesis.overall_summary,
            risk_profile=sec_data,
            sentiment_analysis=sentiment_data,
            technical_indicators=tech_data,
            macro_factors=macro_data,
            projections=synthesis.projections,
            historical_data=historical_data
        )
        
        # Write to cache
        try:
            with open(cache_file, "w") as f:
                json.dump(profile.model_dump(), f, indent=2)
        except Exception as ce:
            print(f"[{ticker}] Failed to write profile cache: {ce}")
            
        return profile
