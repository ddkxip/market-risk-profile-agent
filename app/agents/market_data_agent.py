import yfinance as yf
import pandas as pd
import numpy as np
from app.models import TechnicalIndicatorValues

class MarketDataAgent:
    def __init__(self):
        pass

    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, series: pd.Series) -> tuple[pd.Series, pd.Series]:
        exp1 = series.ewm(span=12, adjust=False).mean()
        exp2 = series.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def get_indicators(self, ticker: str) -> TechnicalIndicatorValues:
        # Fetch 1 year of daily historical data to compute indicators accurately (e.g. 200 SMA)
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        if df.empty:
            raise ValueError(f"No price data found for ticker {ticker}")

        # Basic values
        current_price = float(df['Close'].iloc[-1])

        # Moving Averages
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()

        sma_50_val = float(df['SMA_50'].iloc[-1]) if not pd.isna(df['SMA_50'].iloc[-1]) else current_price
        sma_200_val = float(df['SMA_200'].iloc[-1]) if not pd.isna(df['SMA_200'].iloc[-1]) else current_price

        # Trend status based on current price and SMAs
        if current_price > sma_50_val > sma_200_val:
            trend_status = "Strong Bullish"
        elif current_price > sma_50_val and current_price < sma_200_val:
            trend_status = "Moderately Bullish (Short-term)"
        elif current_price < sma_50_val < sma_200_val:
            trend_status = "Strong Bearish"
        else:
            trend_status = "Neutral / Sideways"

        # RSI calculation
        df['RSI'] = self.calculate_rsi(df['Close'])
        rsi_val = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50.0

        if rsi_val >= 70:
            rsi_status = "Overbought"
        elif rsi_val <= 30:
            rsi_status = "Oversold"
        else:
            rsi_status = "Neutral"

        # MACD calculation
        macd_series, signal_series = self.calculate_macd(df['Close'])
        df['MACD'] = macd_series
        df['MACD_Signal'] = signal_series

        macd_val = float(df['MACD'].iloc[-1])
        macd_sig_val = float(df['MACD_Signal'].iloc[-1])

        # MACD crossover state
        if macd_val > macd_sig_val and df['MACD'].iloc[-2] <= df['MACD_Signal'].iloc[-2]:
            macd_status = "Bullish Crossover (Buy Signal)"
        elif macd_val < macd_sig_val and df['MACD'].iloc[-2] >= df['MACD_Signal'].iloc[-2]:
            macd_status = "Bearish Crossover (Sell Signal)"
        elif macd_val > macd_sig_val:
            macd_status = "Bullish Momentum"
        else:
            macd_status = "Bearish Momentum"

        return TechnicalIndicatorValues(
            current_price=round(current_price, 2),
            rsi_14=round(rsi_val, 2),
            rsi_status=rsi_status,
            macd_value=round(macd_val, 4),
            macd_signal=round(macd_sig_val, 4),
            macd_status=macd_status,
            sma_50=round(sma_50_val, 2),
            sma_200=round(sma_200_val, 2),
            trend_status=trend_status
        )
