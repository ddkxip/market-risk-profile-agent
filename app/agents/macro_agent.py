import asyncio
import sys
import json
import yfinance as yf
from google import genai
from app.config import get_gemini_client, generate_content_with_retry
from app.models import MacroeconomicFactors
from typing import List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

    async def fetch_url_via_mcp(self, url: str) -> str:
        """Helper to fetch a URL using the MCP fetch server stdio connection."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server_fetch"]
        )
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("fetch", arguments={"url": url})
                    if result and result.content:
                        return result.content[0].text
        except Exception as e:
            print(f"[MCP Fetch Error] Failed to fetch {url} via MCP: {e}")
        return ""

    async def fetch_macro_data_async(self) -> tuple[str, str]:
        """Fetches FEDFUNDS and CPI data in parallel via MCP fetch server."""
        fed_task = self.fetch_url_via_mcp("https://fred.stlouisfed.org/series/FEDFUNDS")
        cpi_task = self.fetch_url_via_mcp("https://fred.stlouisfed.org/series/CPIAUCSL")
        return await asyncio.gather(fed_task, cpi_task)

    def analyze_macro_factors_with_gemini(self, ticker: str, sector: str, industry: str, summary: str) -> List[MacroeconomicFactors]:
        """Uses Gemini to evaluate macroeconomic factors, grounded in live FRED data from MCP fetch."""
        # Run MCP fetch asynchronously
        try:
            fed_text, cpi_text = asyncio.run(self.fetch_macro_data_async())
        except Exception as e:
            print(f"Error in macro data async gather: {e}")
            fed_text, cpi_text = "", ""

        client = get_gemini_client()
        
        prompt = f"""
        You are a senior macroeconomic analyst. Evaluate the macroeconomic headwinds and tailwinds facing {ticker} (Sector: {sector}, Industry: {industry}).
        
        Company Context:
        <company_summary>
        {summary[:1000]}
        </company_summary>
        
        Use the following LIVE macroeconomic indicators retrieved from the Federal Reserve Economic Data (FRED) website to ground your analysis:
        
        --- LIVE FRED INTEREST RATE DATA (FEDFUNDS) ---
        <fedfunds_mcp_data>
        {fed_text[:2000] if fed_text else "No live Interest Rate data available."}
        </fedfunds_mcp_data>
        Source URL: https://fred.stlouisfed.org/series/FEDFUNDS
        
        --- LIVE FRED INFLATION DATA (CPIAUCSL) ---
        <cpi_mcp_data>
        {cpi_text[:2000] if cpi_text else "No live Inflation data available."}
        </cpi_mcp_data>
        Source URL: https://fred.stlouisfed.org/series/CPIAUCSL
        
        Ground your analysis of interest rates and inflation in these actual numbers.
        Evaluate the impact of the following macro factors:
        1. Interest Rates / Central Bank Policy (Using the actual current Fed Funds Rate from FEDFUNDS. Cite the source URL: https://fred.stlouisfed.org/series/FEDFUNDS)
        2. Inflation / Consumer Spending (Using the actual current CPI index value from CPIAUCSL and referencing the computed YoY inflation percentage change. Cite the source URL: https://fred.stlouisfed.org/series/CPIAUCSL)
        3. Regulatory / Geopolitical changes (tariffs, supply chain shifts)
        4. Any other major factor highly specific to the {sector} sector.
        
        Generate a list of MacroeconomicFactors, specifying the factor name, its impact level (Positive, Negative, Neutral), and a detailed description of the mechanism of impact including the FRED numbers you retrieved.
        """
        
        from pydantic import BaseModel
        class MacroListContainer(BaseModel):
            factors: List[MacroeconomicFactors]

        response = generate_content_with_retry(
            client=client,
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
