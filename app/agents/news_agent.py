import yfinance as yf
from datetime import datetime
import json
from google import genai
from app.config import get_gemini_client
from app.models import SentimentAnalysis, NewsSentimentItem

class NewsAgent:
    def __init__(self):
        pass

    def get_news_headlines(self, ticker: str, max_items: int = 6) -> list[dict]:
        """Fetches recent news metadata using yfinance."""
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news
            if not news_items:
                return []
                
            formatted_news = []
            for item in news_items[:max_items]:
                # Convert Unix timestamp to readable date
                pub_time = item.get("providerPublishTime")
                date_str = "Recent"
                if pub_time:
                    date_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M')
                    
                formatted_news.append({
                    "headline": item.get("title", ""),
                    "source": item.get("publisher", "Unknown"),
                    "date": date_str,
                    "link": item.get("link", "")
                })
            return formatted_news
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []

    def analyze_sentiment_with_gemini(self, ticker: str, news_data: list[dict]) -> SentimentAnalysis:
        """Passes headlines to Gemini for sentiment evaluation and key takeaways."""
        client = get_gemini_client()
        
        if not news_data:
            # Fallback if no news could be fetched
            prompt = f"""
            You are a stock market sentiment analyst. There are no recent news headlines available for {ticker}.
            Provide an overall sentiment assessment (Bullish/Bearish/Neutral) and sentiment score (-1.0 to 1.0)
            based on your internal knowledge of the market consensus, recent earnings reports, and analyst ratings as of mid-2026.
            Also, generate 3 hypothetical/representative recent news developments with insights for {ticker}.
            """
        else:
            # Serialize news items for the LLM
            news_text = json.dumps(news_data, indent=2)
            prompt = f"""
            You are a stock market sentiment analyst. Analyze the following news headlines for {ticker}.
            For each article, determine the sentiment (Positive, Negative, Neutral) and write a one-sentence key takeaway for investors.
            Calculate an overall sentiment rating (Bullish, Bearish, Neutral) and a score from -1.0 (very bearish) to 1.0 (very bullish).
            
            News Articles:
            {news_text}
            """
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': SentimentAnalysis,
                'temperature': 0.1
            }
        )
        
        return SentimentAnalysis.model_validate_json(response.text)

    def get_sentiment(self, ticker: str) -> SentimentAnalysis:
        """Main entry point to retrieve sentiment profile."""
        news_data = self.get_news_headlines(ticker)
        return self.analyze_sentiment_with_gemini(ticker, news_data)
