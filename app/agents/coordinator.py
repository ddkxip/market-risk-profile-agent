import asyncio
import json
import os
import yfinance as yf
from datetime import datetime
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event
from google.genai import types
import sys
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters
from pydantic import BaseModel, Field

from app.config import get_gemini_client
from app.models import CompanyProfileResponse, Projections
from app.agents.market_data_agent import MarketDataAgent
from app.agents.sec_agent import SECAgent
from app.agents.news_agent import NewsAgent
from app.agents.macro_agent import MacroAgent
from app.agents.forecasting_agent import ForecastingAgent
from app.session_store import SessionStore
from app.skills.guardrails import (
    ground_tool_output, append_disclaimer_and_flag_numbers, block_advice_requests,
)
from app.skills.validators import clamp_forecast


# 1. Wrapper Function Tools for ADK Subagents
market_data_agent = MarketDataAgent()
sec_agent = SECAgent()
news_agent = NewsAgent()
macro_agent = MacroAgent()
forecasting_agent = ForecastingAgent()

def get_market_technicals(ticker: str) -> str:
    """Retrieves current stock price, RSI, MACD, and SMAs for a ticker."""
    try:
        tech_vals, _ = market_data_agent.get_indicators(ticker)
        return json.dumps(tech_vals.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_sec_corporate_risks(ticker: str) -> str:
    """Retrieves SEC filing risk factors, summaries, and source filing URL for a ticker."""
    try:
        profile = sec_agent.get_risk_profile(ticker)
        return json.dumps(profile.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_news_sentiment(ticker: str) -> str:
    """Retrieves recent news headlines, sentiment scores, and article links for a ticker."""
    try:
        sentiment = news_agent.get_sentiment(ticker)
        return json.dumps(sentiment.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_macroeconomic_factors(ticker: str) -> str:
    """Retrieves macroeconomic headwinds and tailwinds impacting the company's sector."""
    try:
        factors = macro_agent.get_macro_factors(ticker)
        return json.dumps([f.model_dump() for f in factors])
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_stock_price_forecast(ticker: str) -> str:
    """Retrieves a 5-day stock price forecast, confidence level, and quantitative rationale."""
    try:
        forecast = forecasting_agent.get_forecast(ticker)
        return json.dumps(forecast.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})

# 2. ADK Subagents Definitions
market_adk_agent = Agent(
    name="market_data_analyst",
    mode="single_turn",
    description="Analyzes stock price trends, RSI, MACD, and SMAs.",
    instruction="Use the get_market_technicals tool to retrieve technical indicators.",
    tools=[get_market_technicals],
    after_tool_callback=ground_tool_output
)

sec_adk_agent = Agent(
    name="sec_filing_analyst",
    mode="single_turn",
    description="Extracts and reviews SEC filing risk factors and CIK mapping.",
    instruction="Use the get_sec_corporate_risks tool to analyze corporate risks.",
    tools=[get_sec_corporate_risks],
    after_tool_callback=ground_tool_output
)

news_adk_agent = Agent(
    name="news_sentiment_analyst",
    mode="single_turn",
    description="Gathers news headlines and sentiment ratings.",
    instruction="Use the get_news_sentiment tool to retrieve recent stock developments.",
    tools=[get_news_sentiment],
    after_tool_callback=ground_tool_output
)

web_tools = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server_fetch"]
        ),
        timeout=30,
    )
)

macro_adk_agent = Agent(
    name="macroeconomics_analyst",
    model="gemini-2.5-flash",
    description="Grounds macroeconomic analysis in live web sources (like FRED) via MCP.",
    instruction="""
    Use the fetch tool to retrieve current macro indicators (FEDFUNDS, CPI, etc.) from the Federal Reserve Economic Data (FRED) website:
    - FEDFUNDS (Interest Rates): https://fred.stlouisfed.org/series/FEDFUNDS
    - CPI (Inflation): https://fred.stlouisfed.org/series/CPIAUCSL
    
    Fetch these pages to extract the latest interest rate and inflation figures.
    Analyze how these current interest rates, inflation, and sector headwinds/tailwinds impact the company's sector.
    Provide the exact figures you retrieved, and cite the FRED source URLs.
    Do NOT rely on prior training knowledge for current macro figures.
    """,
    tools=[web_tools],
    after_tool_callback=ground_tool_output
)

forecast_adk_agent = Agent(
    name="forecasting_analyst",
    mode="single_turn",
    description="Projects future stock prices using quantitative trends.",
    instruction="Use the get_stock_price_forecast tool to project 5-day price series.",
    tools=[get_stock_price_forecast],
    after_tool_callback=ground_tool_output
)

# 3. Root ADK Coordinator
coordinator_adk_agent = Agent(
    name="portfolio_coordinator",
    model="gemini-2.5-flash",
    description="Chief investment officer coordinating specialized financial analysts.",
    instruction="""
    You are the Chief Investment Officer. Your goal is to answer investor questions about stocks.
    You will be provided with the active stock's compiled profile details in the message prefix: [Active Stock Profile Context for TICKER: ...].
    If the investor asks about the active stock (e.g. its price, trend, 5-day forecast, SEC risks, sentiment, or news), you MUST answer directly using the provided profile context. Do NOT call your sub-agents in this case, as you already have the compiled data.
    If the investor asks about a different stock, or wants to run a new comparison, delegate to your sub-agents:
    - market_data_analyst for prices, trends, RSI, MACD, SMAs.
    - sec_filing_analyst for corporate risk factors and filing URLs.
    - news_sentiment_analyst for headlines and sentiment scores.
    - macroeconomics_analyst for sector tailwinds/headwinds.
    - forecasting_analyst for 5-day daily price projections.
    
    Synthesize findings into a cohesive, professional conversational reply. Refer to conversation history to maintain context.
    """,
    sub_agents=[market_adk_agent, sec_adk_agent, news_adk_agent, macro_adk_agent, forecast_adk_agent],
    before_model_callback=block_advice_requests,
    after_model_callback=append_disclaimer_and_flag_numbers
)

class SynthesizedFields(BaseModel):
    overall_summary: str = Field(..., description="High-level investor summary")
    projections: Projections = Field(..., description="Short-term and long-term outlooks")

class CoordinatorAgent:
    def __init__(self):
        self.market_agent = market_data_agent
        self.sec_agent = sec_agent
        self.news_agent = news_agent
        self.macro_agent = macro_agent
        self.forecasting_agent = forecasting_agent
        self.root_adk_agent = coordinator_adk_agent

    def get_company_name(self, ticker: str) -> str:
        """Retrieves the full company name using yfinance."""
        try:
            stock = yf.Ticker(ticker)
            return stock.info.get("longName", ticker)
        except Exception:
            return ticker

    def resolve_ticker(self, query: str) -> str:
        """Attempts to resolve a company name query to a valid ticker using SEC tickers database (cached)."""
        query_clean = query.upper().strip()
        if not query_clean:
            return query
            
        if query_clean.isalpha() and 1 <= len(query_clean) <= 5:
            return query_clean
            
        try:
            from app.agents.sec_agent import load_sec_tickers
            headers = {"User-Agent": "MarketRiskAgent/1.0 (ddkxi@gemini-capstone.com)"}
            data = load_sec_tickers(headers)
                
            for company in data.values():
                title = company.get('title', '').upper()
                ticker_symbol = company.get('ticker', '').upper()
                if query_clean in title or title in query_clean:
                    print(f"[Resolver] Resolved '{query}' to ticker '{ticker_symbol}'")
                    return ticker_symbol
        except Exception as e:
            print(f"Error in ticker resolver: {e}")
            
        return query_clean

    def generate_profile(self, ticker: str, custom_company_name: str = None) -> CompanyProfileResponse:
        """Synchronous wrapper for offline test scripts and CLI testing."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.generate_profile_async(ticker, custom_company_name=custom_company_name))
        finally:
            loop.close()

    async def generate_profile_async(self, ticker: str, session_id: str = None, custom_company_name: str = None) -> CompanyProfileResponse:
        """Asynchronously compiles risk and trading profile concurrently, caching results."""
        ticker = self.resolve_ticker(ticker)
        
        # Check cache
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_dir = os.path.join(base_dir, ".cache", "profiles")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{ticker.lower()}_profile.json")
        
        # Cache duration: 2 hours (7200 seconds)
        if os.path.exists(cache_file):
            try:
                mtime = os.path.getmtime(cache_file)
                import time
                if time.time() - mtime < 7200:
                    print(f"[{ticker}] Loading FULL company profile from cache...")
                    with open(cache_file, "r") as f:
                        cached_data = json.load(f)
                    profile = CompanyProfileResponse.model_validate(cached_data)
                    
                    if session_id:
                        db = SessionStore()
                        db.update_metadata(session_id, last_ticker=ticker)
                        db.save_message(session_id, "user", f"Analyze {ticker}")
                        db.save_message(session_id, "model", f"Loaded cached profile for {profile.company_name} ({profile.ticker}).")
                    return profile
            except Exception as ce:
                print(f"[{ticker}] Failed to load cached profile: {ce}")

        print(f"[{ticker}] Starting parallel profile synthesis...")

        # Concurrent, parallel fetching using asyncio.to_thread
        tech_future = asyncio.to_thread(self.market_agent.get_indicators, ticker)
        sec_future = asyncio.to_thread(self.sec_agent.get_risk_profile, ticker)
        news_future = asyncio.to_thread(self.news_agent.get_sentiment, ticker)
        macro_future = asyncio.to_thread(self.macro_agent.get_macro_factors, ticker)
        forecast_future = asyncio.to_thread(self.forecasting_agent.get_forecast, ticker)
        
        (tech_data, historical_data), sec_data, sentiment_data, macro_data, forecast_data = await asyncio.gather(
            tech_future, sec_future, news_future, macro_future, forecast_future
        )

        # Deterministically clamp the forecasted stock price series to +/- 25% daily move limit
        if forecast_data and tech_data and hasattr(tech_data, "current_price") and tech_data.current_price:
            forecast_data, repairs = clamp_forecast(forecast_data, tech_data.current_price)
            if repairs:
                print(f"[{ticker}] Grounding Validator: Clamped unrealistic forecast: {repairs}")

        company_name = custom_company_name or self.get_company_name(ticker)

        # Synthesis
        client = get_gemini_client()
        
        context_str = f"""
        Company: {company_name} ({ticker})
        Date: {datetime.now().strftime('%Y-%m-%d')}
        
        --- TECHNICAL TRENDS ---
        Current Price: ${tech_data.current_price}
        RSI (14): {tech_data.rsi_14} ({tech_data.rsi_status})
        MACD: {tech_data.macd_value} (Status: {tech_data.macd_status})
        
        --- SEC FILING RISKS ---
        Overall SEC Risk Rating: {sec_data.overall_rating}
        SEC Risk Summary: {sec_data.summary}
        """
        for factor in sec_data.factors:
            context_str += f"\n- [{factor.category} | Severity: {factor.severity}] {factor.description}"
            
        context_str += f"""
        
        --- NEWS & SENTIMENT ---
        Overall Sentiment: {sentiment_data.overall_sentiment} (Score: {sentiment_data.score})
        """
        for item in sentiment_data.items:
            context_str += f"\n- {item.headline} (Takeaway: {item.takeaway})"
            
        context_str += f"""
        
        --- FORECAST ---
        Forecast (Next 5 Days):
        """
        for pt in forecast_data.points:
            context_str += f"\n- {pt.date}: ${pt.price}"
            
        prompt = f"""
        You are the Chief Investment Officer. Synthesize the following dataset for {company_name} ({ticker}) into an overall investor summary and projections.
        
        Company Analysis Data:
        {context_str}
        
        Write:
        1. An overall_summary (a paragraph of ~100-150 words).
        2. Projections:
           - short_term: Short-term projection (1-3 months).
           - long_term: Long-term projection (12+ months).
        """
        
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
            historical_data=historical_data,
            forecast=forecast_data
        )
        
        # Write to cache
        try:
            with open(cache_file, "w") as f:
                json.dump(profile.model_dump(), f, indent=2)
        except Exception as ce:
            print(f"[{ticker}] Failed to write profile cache: {ce}")

        # Update SQLite session store
        if session_id:
            db = SessionStore()
            db.update_metadata(session_id, last_ticker=ticker)
            db.save_message(session_id, "user", f"Analyze {ticker}")
            db.save_message(session_id, "model", f"Generated complete risk profile for {company_name} ({ticker}). Overall summary: {profile.overall_summary}")
            
        return profile

    async def chat_async(self, message: str, session_id: str, user_id: str = "default_user") -> str:
        """Sends user message to ADK agent team, leveraging SQLite session history and context."""
        db = SessionStore()
        history = db.get_history(session_id)
        metadata = db.get_metadata(session_id)
        
        # Load ADK session service
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="alpha_insight",
            user_id=user_id,
            session_id=session_id
        )
        
        # Populate session events from SQLite history
        for msg in history:
            role = 'user' if msg['role'] == 'user' else 'model'
            event = Event(
                author=role,
                content=types.Content(role=role, parts=[types.Part(text=msg['content'])]),
            )
            session.events.append(event)
            
        # Stash grounded numbers in the session state dictionary so they can be verified by the guardrail callback
        grounded_numbers = []
        if metadata.get("last_ticker"):
            ticker = metadata["last_ticker"]
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_file = os.path.join(base_dir, ".cache", "profiles", f"{ticker.lower()}_profile.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r") as f:
                        profile_data = json.load(f)
                    
                    # Core indicators
                    curr_price = profile_data.get("technical_indicators", {}).get("current_price")
                    if curr_price is not None:
                        grounded_numbers.append(float(curr_price))
                    
                    rsi = profile_data.get("technical_indicators", {}).get("rsi_14")
                    if rsi is not None:
                        grounded_numbers.append(float(rsi))
                    
                    score = profile_data.get("sentiment_analysis", {}).get("score")
                    if score is not None:
                        grounded_numbers.append(float(score))
                    
                    # 5-day Forecast points
                    for pt in profile_data.get("forecast", {}).get("points", []):
                        if pt.get("price") is not None:
                            grounded_numbers.append(float(pt["price"]))
                except Exception as e:
                    print(f"Error stashing grounded numbers: {e}")
        
        if grounded_numbers:
            session.state["grounded_numbers"] = grounded_numbers
            
        runner = Runner(agent=self.root_adk_agent, app_name="alpha_insight", session_service=session_service)
        
        # Prepend the active stock context to the prompt so the ADK agent knows what stock we are discussing
        prefix = ""
        if metadata.get("last_ticker"):
            ticker = metadata["last_ticker"]
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_file = os.path.join(base_dir, ".cache", "profiles", f"{ticker.lower()}_profile.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r") as f:
                        profile_data = json.load(f)
                    # Exclude large timeseries list to stay fast and cheap
                    if "historical_data" in profile_data:
                        del profile_data["historical_data"]
                    prefix = f"[Active Stock Profile Context for {ticker}:\n{json.dumps(profile_data)}]\n"
                except Exception:
                    prefix = f"[Active Stock Ticker context: {ticker}]\n"
            else:
                prefix = f"[Active Stock Ticker context: {ticker}]\n"
            
        new_content = types.Content(role='user', parts=[types.Part(text=f"{prefix}{message}")])
        final_text = "Sorry, I could not compile a response."
        
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                    break
                    
        # Save new turn in SQLite
        db.save_message(session_id, "user", message)
        db.save_message(session_id, "model", final_text)
        
        return final_text
