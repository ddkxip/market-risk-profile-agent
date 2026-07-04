from datetime import datetime
import yfinance as yf
from google import genai
from app.config import get_gemini_client
from app.models import CompanyProfileResponse, Projections
from app.agents.market_data_agent import MarketDataAgent
from app.agents.sec_agent import SECAgent
from app.agents.news_agent import NewsAgent
from app.agents.macro_agent import MacroAgent

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

    def generate_profile(self, ticker: str, custom_company_name: str = None) -> CompanyProfileResponse:
        ticker = ticker.upper().strip()
        print(f"[{ticker}] Starting profile synthesis...")

        # 1. Gather all sub-agent data
        # Technical indicators
        tech_data = self.market_agent.get_indicators(ticker)
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
        class SynthesisResponse(BaseModel := type('SynthesisResponse', (), {})):
            # We can use a small Pydantic model for just the synthesized fields
            from pydantic import BaseModel, Field
            class SynthesizedFields(BaseModel):
                overall_summary: str = Field(..., description="High-level investor summary")
                projections: Projections = Field(..., description="Short-term and long-term outlooks")
            
        from pydantic import BaseModel, Field
        class SynthesizedFields(BaseModel):
            overall_summary: str = Field(..., description="High-level investor summary")
            projections: Projections = Field(..., description="Short-term and long-term outlooks")

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
        return CompanyProfileResponse(
            ticker=ticker,
            company_name=company_name,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            overall_summary=synthesis.overall_summary,
            risk_profile=sec_data,
            sentiment_analysis=sentiment_data,
            technical_indicators=tech_data,
            macro_factors=macro_data,
            projections=synthesis.projections
        )
