import os
import sys
import time
import asyncio
from datetime import datetime

# Adjust path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.coordinator import CoordinatorAgent
from app.models import CompanyProfileResponse

# List of 12 diverse tickers to evaluate
TEST_TICKERS = [
    "AAPL",  # Technology
    "MSFT",  # Technology
    "GOOGL", # Alphabet
    "AMZN",  # Consumer Cyclical
    "TSLA",  # Automotive
    "NVDA",  # Semiconductors
    "META",  # Communication Services
    "NFLX",  # Entertainment
    "COST",  # Consumer Defensive
    "PEP",   # Consumer Defensive
    "AVGO",  # Broadcom
    "AMD"    # Advanced Micro Devices
]

async def run_single_eval(coordinator: CoordinatorAgent, ticker: str) -> dict:
    """Evaluates a single ticker and asserts data properties, returning status and latency."""
    print(f"\n[Eval] Testing {ticker}...")
    start_time = time.time()
    
    result = {
        "ticker": ticker,
        "status": "PASS",
        "latency_sec": 0.0,
        "errors": []
    }
    
    try:
        # Run profile synthesis asynchronously
        profile: CompanyProfileResponse = await coordinator.generate_profile_async(ticker)
        result["latency_sec"] = time.time() - start_time
        
        # Assertion 1: Basic Metadata
        if not profile.company_name or profile.company_name == ticker:
            result["errors"].append("Company name was not resolved successfully.")
            
        # Assertion 2: Technical Indicators
        techs = profile.technical_indicators
        if not (0.0 <= techs.rsi_14 <= 100.0):
            result["errors"].append(f"RSI-14 value {techs.rsi_14} out of range [0, 100].")
        if techs.current_price <= 0:
            result["errors"].append(f"Current price {techs.current_price} is negative/zero.")
        if techs.trend_status not in ["Strong Bullish", "Moderately Bullish (Short-term)", "Strong Bearish", "Neutral / Sideways"]:
            result["errors"].append(f"Invalid trend status: {techs.trend_status}")
            
        # Assertion 3: SEC Risk Profile
        sec = profile.risk_profile
        if not sec.factors:
            result["errors"].append("SEC risk factors list is empty.")
        if not sec.summary:
            result["errors"].append("SEC risk summary is empty.")
        if not sec.filing_url or not sec.filing_url.startswith("https://www.sec.gov/"):
            result["errors"].append(f"SEC filing URL '{sec.filing_url}' is invalid or missing.")
            
        # Assertion 4: News Sentiment
        news = profile.sentiment_analysis
        if not (-1.0 <= news.score <= 1.0):
            result["errors"].append(f"Sentiment score {news.score} out of range [-1.0, 1.0].")
        if news.overall_sentiment not in ["Bullish", "Bearish", "Neutral"]:
            result["errors"].append(f"Invalid news sentiment status: {news.overall_sentiment}")
            
        # Assertion 5: 5-Day Forecast
        forecast = profile.forecast
        if not forecast:
            result["errors"].append("Forecast object is missing.")
        else:
            if len(forecast.points) != 5:
                result["errors"].append(f"Expected exactly 5 forecast points, got {len(forecast.points)}.")
            for i, pt in enumerate(forecast.points):
                if pt.price <= 0:
                    result["errors"].append(f"Forecast point {i+1} price {pt.price} is negative/zero.")
                try:
                    datetime.strptime(pt.date, "%Y-%m-%d")
                except ValueError:
                    result["errors"].append(f"Forecast point {i+1} date '{pt.date}' has invalid format (expected YYYY-MM-DD).")
            if forecast.confidence_level not in ["High", "Medium", "Low"]:
                result["errors"].append(f"Invalid forecast confidence level: {forecast.confidence_level}")
                
        # Assertion 6: Macro factors
        if not profile.macro_factors:
            result["errors"].append("Macro factors list is empty.")
            
    except Exception as e:
        result["latency_sec"] = time.time() - start_time
        result["status"] = "FAIL"
        result["errors"].append(f"Unhandled execution error: {str(e)}")
        
    if result["errors"]:
        result["status"] = "FAIL"
        
    return result

async def main():
    print("=" * 60)
    print("      AlphaInsight Multi-Agent Copilot Evaluation Suite      ")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    coordinator = CoordinatorAgent()
    
    passed_count = 0
    total_latency = 0.0
    results = []
    
    # Process each ticker sequentially to observe logs
    for ticker in TEST_TICKERS:
        res = await run_single_eval(coordinator, ticker)
        results.append(res)
        if res["status"] == "PASS":
            passed_count += 1
        total_latency += res["latency_sec"]
        
    print("\n" + "=" * 60)
    print("                     EVALUATION SUMMARY                     ")
    print("=" * 60)
    print(f"{'Ticker':<10} | {'Status':<8} | {'Latency (s)':<12} | {'Issues Found'}")
    print("-" * 60)
    for res in results:
        issues_str = "; ".join(res["errors"]) if res["errors"] else "None"
        print(f"{res['ticker']:<10} | {res['status']:<8} | {res['latency_sec']:<12.2f} | {issues_str}")
        
    print("-" * 60)
    avg_latency = total_latency / len(TEST_TICKERS)
    print(f"Total Tickers: {len(TEST_TICKERS)}")
    print(f"Passed:        {passed_count} / {len(TEST_TICKERS)}")
    print(f"Avg Latency:   {avg_latency:.2f} seconds")
    print("=" * 60)
    
    if passed_count < len(TEST_TICKERS):
        print("[FAIL] One or more tickers failed assertions.")
        sys.exit(1)
    else:
        print("[PASS] All tickers passed evaluations successfully!")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
