import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from google import genai
from app.config import get_gemini_client
from app.models import ForecastData, ForecastPoint

class ForecastingAgent:
    def __init__(self):
        pass

    def get_forecast(self, ticker: str) -> ForecastData:
        """Fetches the last 30 trading days of data and uses Gemini to forecast the next 5 trading days."""
        ticker = ticker.upper().strip()
        
        # 1. Fetch 30 days of historical prices
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2mo") # Grab 2 months to ensure we get at least 30 trading days
            if hist.empty:
                raise ValueError(f"No price history found for {ticker}")
            
            # Select the last 30 trading days
            hist_subset = hist.tail(30)
            
            prices_data = []
            for date_ts, row in hist_subset.iterrows():
                date_str = date_ts.strftime('%Y-%m-%d')
                prices_data.append(f"{date_str}: ${row['Close']:.2f}")
                
            prices_series_str = "\n".join(prices_data)
            last_price = hist_subset['Close'].iloc[-1]
            last_date = hist_subset.index[-1]
            
            # 2. Project the next 5 future trading days (skipping weekends)
            future_dates = []
            current_date = last_date
            while len(future_dates) < 5:
                current_date += timedelta(days=1)
                # 5 = Saturday, 6 = Sunday
                if current_date.weekday() < 5:
                    future_dates.append(current_date.strftime('%Y-%m-%d'))
                    
            future_dates_str = ", ".join(future_dates)
            
        except Exception as e:
            print(f"Error gathering prices for forecasting on {ticker}: {e}")
            # Fallback mock setup if yfinance fails
            prices_series_str = "No historical price series available."
            last_price = 100.0
            future_dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 6)]
            future_dates_str = ", ".join(future_dates)

        # 3. Call Gemini to forecast
        client = get_gemini_client()
        
        prompt = f"""
        You are a quantitative financial analyst and time series forecasting assistant.
        Analyze the following historical closing prices for {ticker} over the last 30 trading days:
        ---
        {prices_series_str}
        ---
        
        The last recorded closing price was ${last_price:.2f}.
        
        Forecast the closing prices for the next 5 future trading days on these dates:
        {future_dates_str}
        
        Write:
        1. points: A list of 5 projected daily points (using the requested future dates and forecasted closing prices). Make sure the forecasted prices are mathematically reasonable based on the recent trend (avoid unrealistic spikes/crashes unless historical volatility warrants it).
        2. confidence_level: Confidence level of your forecast (High, Medium, or Low).
        3. reasoning: A detailed analytical breakdown (1-2 paragraphs) explaining your projection based on the trend momentum, moving averages, and support/resistance levels.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': ForecastData,
                'temperature': 0.2
            }
        )
        
        return ForecastData.model_validate_json(response.text)
