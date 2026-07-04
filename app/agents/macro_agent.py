import yfinance as yf
from google import genai
from app.config import get_gemini_client
from app.models import MacroeconomicFactors
from typing import List

class MacroAgent:
    def __init__(self):
        pass

    def get_company_sector_info(self, ticker: str) -> tuple[str, str, str]:
        """Fetches sector, industry, and description from yfinance."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get("sector", "Unknown")
            industry = info.get("industry", "Unknown")
            summary = info.get("longBusinessSummary", "")
            return sector, industry, summary
        except Exception as e:
            print(f"Error fetching sector info for {ticker}: {e}")
            return "Unknown", "Unknown", ""

    def analyze_macro_factors_with_gemini(self, ticker: str, sector: str, industry: str, summary: str) -> List[MacroeconomicFactors]:
        """Uses Gemini to evaluate macroeconomic factors impacting the company's specific sector."""
        client = get_gemini_client()
        
        prompt = f"""
        You are a macroeconomic analyst. Evaluate the macroeconomic headwinds and tailwinds facing {ticker} (Sector: {sector}, Industry: {industry}).
        
        Company Context:
        {summary[:1000]}
        
        Evaluate the impact of the following macro factors as of 2026:
        1. Interest Rates / Central Bank Policy
        2. Inflation / Consumer Spending
        3. Regulatory / Geopolitical changes (e.g. tariffs, supply chain shifts)
        4. Any other major factor highly specific to the {sector} sector.
        
        Generate a list of MacroeconomicFactors, specifying the factor name, its impact level (Positive, Negative, Neutral), and a detailed description of the mechanism of impact.
        """
        
        # Pydantic List Wrapper for Schema
        # In Gemini python SDK, list schemas are specified by passing List[Model] or creating a container class.
        # Let's define a local container model for the list to ensure schema compliance.
        from pydantic import BaseModel
        class MacroListContainer(BaseModel):
            factors: List[MacroeconomicFactors]

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': MacroListContainer,
                'temperature': 0.2
            }
        )
        
        container = MacroListContainer.model_validate_json(response.text)
        return container.factors

    def get_macro_factors(self, ticker: str) -> List[MacroeconomicFactors]:
        """Main entry point to retrieve macro factors."""
        sector, industry, summary = self.get_company_sector_info(ticker)
        return self.analyze_macro_factors_with_gemini(ticker, sector, industry, summary)
