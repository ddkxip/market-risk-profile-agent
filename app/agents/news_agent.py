import yfinance as yf
from datetime import datetime
import json
import urllib.request
import xml.etree.ElementTree as ET
import email.utils
from google import genai
from app.config import get_gemini_client
from app.models import SentimentAnalysis, NewsSentimentItem

class NewsAgent:
    def __init__(self):
        pass

    def get_news_headlines(self, ticker: str, max_items: int = 8) -> list[dict]:
        """Fetches recent news metadata for a ticker, prioritizing Google News search RSS and falling back to yfinance."""
        ticker = ticker.upper().strip()
        formatted_news = []
        
        # 1. Try Google News RSS search for highly company-specific stock news
        try:
            url = f"https://news.google.com/rss/search?q={ticker}+stock"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            
            for item in items[:max_items]:
                title_text = item.find('title').text or ""
                source_text = item.find('source').text if item.find('source') is not None else "Google News"
                link = item.find('link').text or ""
                pub_date = item.find('pubDate').text
                
                # Format date cleanly using email.utils to parse RFC 822 format
                date_str = "Recent"
                if pub_date:
                    try:
                        dt = email.utils.parsedate_to_datetime(pub_date)
                        date_str = dt.strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        date_str = pub_date
                
                # Clean up headline by removing the trailing source (e.g. " - Yahoo Finance")
                if title_text.endswith(f" - {source_text}"):
                    headline = title_text[:-len(f" - {source_text}")]
                else:
                    parts = title_text.rsplit(" - ", 1)
                    headline = parts[0] if len(parts) > 1 else title_text
                    
                formatted_news.append({
                    "headline": headline,
                    "source": source_text,
                    "date": date_str,
                    "link": link
                })
                
            if formatted_news:
                print(f"[{ticker}] Retrieved {len(formatted_news)} company-specific news articles from Google News RSS.")
                return formatted_news
                
        except Exception as ge:
            print(f"Google News RSS fetch failed for {ticker}: {ge}. Falling back to yfinance news feed...")
            
        # 2. Fallback to yfinance news feed if Google News search fails
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news
            if not news_items:
                return []
                
            for item in news_items[:max_items]:
                if not item:
                    continue
                content = item.get("content") or {}
                
                title = content.get("title") or item.get("title") or ""
                provider = content.get("provider") or {}
                publisher = provider.get("displayName") or item.get("publisher") or "Unknown"
                pub_date = content.get("pubDate") or item.get("pubDate")
                pub_time = item.get("providerPublishTime")
                
                date_str = "Recent"
                if pub_date:
                    date_str = pub_date.replace("T", " ").replace("Z", "")
                    if len(date_str) > 16:
                        date_str = date_str[:16]
                elif pub_time:
                    date_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M')
                
                click_url = content.get("clickThroughUrl") or {}
                canonical_url = content.get("canonicalUrl") or {}
                link = click_url.get("url") or canonical_url.get("url") or item.get("link") or ""
                
                formatted_news.append({
                    "headline": title,
                    "source": publisher,
                    "date": date_str,
                    "link": link
                })
            print(f"[{ticker}] Retrieved {len(formatted_news)} news articles from yfinance fallback feed.")
            return formatted_news
        except Exception as e:
            print(f"Error fetching yfinance news fallback for {ticker}: {e}")
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
            # Pass clean metadata to Gemini (we omit links here to keep the prompt clean and save tokens)
            news_prompt_data = [
                {
                    "index": idx,
                    "headline": item["headline"],
                    "source": item["source"],
                    "date": item["date"]
                }
                for idx, item in enumerate(news_data)
            ]
            news_text = json.dumps(news_prompt_data, indent=2)
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
        
        result = SentimentAnalysis.model_validate_json(response.text)
        
        # Post-process to restore correct original headlines and links
        if news_data:
            for idx, item in enumerate(result.items):
                if idx < len(news_data):
                    item.headline = news_data[idx].get("headline", item.headline)
                    item.link = news_data[idx].get("link")
                    item.source = news_data[idx].get("source", item.source)
                    item.date = news_data[idx].get("date", item.date)
                    
        return result

    def get_sentiment(self, ticker: str) -> SentimentAnalysis:
        """Main entry point to retrieve sentiment profile."""
        news_data = self.get_news_headlines(ticker)
        return self.analyze_sentiment_with_gemini(ticker, news_data)
