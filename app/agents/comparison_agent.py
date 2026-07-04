from datetime import datetime
from google import genai
from pydantic import BaseModel, Field
from app.config import get_gemini_client
from app.models import CompanyProfileResponse, ComparisonResponse
from app.agents.coordinator import CoordinatorAgent

class ComparativeFields(BaseModel):
    comparative_summary: str = Field(..., description="Side-by-side comparative summary of the two companies")
    better_investment: str = Field(..., description="Bottom-line risk-adjusted comparison and investment recommendation")

class ComparisonAgent:
    def __init__(self):
        self.coordinator = CoordinatorAgent()

    def compare_companies(self, ticker_a: str, ticker_b: str) -> ComparisonResponse:
        # 1. Resolve and generate/load profiles
        # Note: self.coordinator.generate_profile internally resolves names to tickers and utilizes cache
        profile_a = self.coordinator.generate_profile(ticker_a)
        profile_b = self.coordinator.generate_profile(ticker_b)

        # 2. Query Gemini for comparative analysis
        client = get_gemini_client()
        
        prompt = f"""
        You are a senior portfolio manager. Compare two companies:
        
        --- COMPANY A ---
        Name: {profile_a.company_name} ({profile_a.ticker})
        Current Price: ${profile_a.technical_indicators.current_price}
        Technical Trend: {profile_a.technical_indicators.trend_status} (RSI: {profile_a.technical_indicators.rsi_14})
        Overall Sentiment: {profile_a.sentiment_analysis.overall_sentiment} (Score: {profile_a.sentiment_analysis.score})
        Corporate Risk Level: {profile_a.risk_profile.overall_rating}
        Executive Summary: {profile_a.overall_summary}
        
        --- COMPANY B ---
        Name: {profile_b.company_name} ({profile_b.ticker})
        Current Price: ${profile_b.technical_indicators.current_price}
        Technical Trend: {profile_b.technical_indicators.trend_status} (RSI: {profile_b.technical_indicators.rsi_14})
        Overall Sentiment: {profile_b.sentiment_analysis.overall_sentiment} (Score: {profile_b.sentiment_analysis.score})
        Corporate Risk Level: {profile_b.risk_profile.overall_rating}
        Executive Summary: {profile_b.overall_summary}
        
        Perform a thorough side-by-side comparison:
        1. Compare their relative technical momentum and news sentiments.
        2. Contrast their corporate risk profiles (extracted from SEC filings) and macroeconomic exposure.
        3. Write a comparative_summary (150-200 words) summarizing key points of comparison.
        4. Write a better_investment recommendation (100-150 words) explaining which stock represents a better risk-reward opportunity for investors under current conditions and why.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': ComparativeFields,
                'temperature': 0.3
            }
        )
        
        synthesis = ComparativeFields.model_validate_json(response.text)
        
        return ComparisonResponse(
            profile_a=profile_a,
            profile_b=profile_b,
            comparative_summary=synthesis.comparative_summary,
            better_investment=synthesis.better_investment,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
