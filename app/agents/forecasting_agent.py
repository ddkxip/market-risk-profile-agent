import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from google import genai
from app.config import get_gemini_client, generate_content_with_retry
from app.models import ForecastData, ForecastPoint

class ForecastingAgent:
    def __init__(self):
        pass

    def _calculate_holt_linear_forecast(self, prices: list[float], steps: int = 5, alpha: float = 0.3, beta: float = 0.1) -> list[float]:
        """Applies Holt's Linear Trend (Double Exponential Smoothing) to project future prices."""
        if len(prices) < 2:
            return [prices[-1]] * steps if prices else [0.0] * steps
        
        # Initialize level and trend
        level = prices[0]
        trend = prices[1] - prices[0]
        
        for i in range(1, len(prices)):
            y = prices[i]
            last_level = level
            level = alpha * y + (1 - alpha) * (level + trend)
            trend = beta * (level - last_level) + (1 - beta) * trend
            
        forecast = []
        for h in range(1, steps + 1):
            val = level + h * trend
            forecast.append(max(0.01, round(val, 2)))
        return forecast

    def get_forecast(self, ticker: str) -> ForecastData:
        """Fetches 30 trading days of data, runs a Holt's Linear Trend quantitative forecast, and uses Gemini to explain it."""
        ticker = ticker.upper().strip()
        
        # 1. Fetch 30 days of historical prices
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2mo") # Grab 2 months to ensure we get at least 30 trading days
        if hist.empty:
            raise ValueError(f"No price history found for {ticker}. Could not calculate forecast.")
        
        # Select the last 30 trading days
        hist_subset = hist.tail(30)
        if len(hist_subset) < 5:
            raise ValueError(f"Insufficient price history for {ticker} (found {len(hist_subset)} days, need at least 5) to forecast.")
        
        prices_list = hist_subset['Close'].tolist()
        prices_data = []
        for date_ts, row in hist_subset.iterrows():
            date_str = date_ts.strftime('%Y-%m-%d')
            prices_data.append(f"{date_str}: ${row['Close']:.2f}")
            
        prices_series_str = "\n".join(prices_data)
        last_price = prices_list[-1]
        last_date = hist_subset.index[-1]
        
        # 2. Project the next 5 future trading days (skipping weekends)
        future_dates = []
        current_date = last_date
        while len(future_dates) < 5:
            current_date += timedelta(days=1)
            # 5 = Saturday, 6 = Sunday
            if current_date.weekday() < 5:
                future_dates.append(current_date)
                
        future_dates_str = ", ".join([d.strftime('%Y-%m-%d') for d in future_dates])
        
        # 3. Calculate Holt's Quantitative Forecast
        projected_prices = self._calculate_holt_linear_forecast(prices_list, steps=5)
        
        # Format model projection text
        model_projection_items = []
        for d, p in zip(future_dates, projected_prices):
            model_projection_items.append(f"{d.strftime('%Y-%m-%d')}: ${p:.2f}")
        quantitative_forecast_str = "\n".join(model_projection_items)
        
        # 4. Call Gemini to explain the quantitative forecast
        client = get_gemini_client()
        
        prompt = f"""
        You are a quantitative financial analyst. 
        We have calculated a 5-day stock price forecast for {ticker} using a Holt's Linear Trend (Double Exponential Smoothing) quantitative model.
        
        Historical closing prices for the last 30 trading days:
        <historical_prices>
        {prices_series_str}
        </historical_prices>
        
        The last recorded closing price was ${last_price:.2f}.
        
        Our quantitative Holt's Linear Trend model projected the following prices:
        <model_projection>
        {quantitative_forecast_str}
        </model_projection>
        
        Provide your final analysis in JSON matching the schema:
        1. points: A list of 5 projected daily points (using the dates {future_dates_str} and the EXACT forecasted prices calculated by our model). Do NOT modify the forecasted prices.
        2. confidence_level: Assess the confidence of this forecast (High, Medium, or Low) based on the historical volatility and trend strength.
        3. reasoning: Explain the quantitative model's projection. Discuss the trend direction, the smoothed level, historical support/resistance, and how recent momentum influenced the Holt's model.
        """
        
        response = generate_content_with_retry(
            client=client,
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': ForecastData,
                'temperature': 0.1
            }
        )
        
        return ForecastData.model_validate_json(response.text)
