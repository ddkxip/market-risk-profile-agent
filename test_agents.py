import sys
import argparse
from dotenv import load_dotenv
from app.agents.coordinator import CoordinatorAgent
from app.config import get_gemini_client

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Test AlphaInsight Multi-Agent Copilot CLI")
    parser.add_argument("ticker", type=str, help="Stock ticker symbol (e.g. AAPL, MSFT)")
    args = parser.parse_args()
    
    try:
        get_gemini_client()
    except ValueError as e:
        print(f"WARNING: Gemini client configuration error: {e}")
        print("Please configure credentials before running this script.")
        sys.exit(1)
        
    ticker = args.ticker.upper().strip()
    print(f"Starting test analysis for {ticker}...")
    
    coordinator = CoordinatorAgent()
    try:
        profile = coordinator.generate_profile(ticker)
        print("\n" + "="*50)
        print(f"ANALYSIS PROFILE FOR {profile.company_name} ({profile.ticker})")
        print("="*50)
        print(f"Generated at: {profile.generated_at}")
        print(f"Current price: ${profile.technical_indicators.current_price}")
        print(f"Overall Sentiment: {profile.sentiment_analysis.overall_sentiment} (Score: {profile.sentiment_analysis.score})")
        print(f"Overall Corporate Risk: {profile.risk_profile.overall_rating}")
        print(f"Technical Trend: {profile.technical_indicators.trend_status}")
        
        print("\n--- Executive Summary ---")
        print(profile.overall_summary)
        
        print("\n--- Short Term Projection (1-3 Mo) ---")
        print(profile.projections.short_term)
        
        print("\n--- Long Term Projection (12+ Mo) ---")
        print(profile.projections.long_term)
        
        print("\n--- Top news takeaway ---")
        if profile.sentiment_analysis.items:
            print(f"Headline: {profile.sentiment_analysis.items[0].headline}")
            print(f"Takeaway: {profile.sentiment_analysis.items[0].takeaway}")
            
        print("\n--- Top SEC Risk Factor ---")
        if profile.risk_profile.factors:
            print(f"[{profile.risk_profile.factors[0].category}] {profile.risk_profile.factors[0].description}")
            
        print("="*50)
        print("CLI Test Completed Successfully!")
    except Exception as e:
        print(f"Error during CLI test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
