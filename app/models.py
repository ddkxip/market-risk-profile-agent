import uuid
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

def _is_valid_uuid4(val: str) -> bool:
    try:
        uuid.UUID(val, version=4)
        return True
    except ValueError:
        return False

class AnalysisRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL, MSFT, GOOGL)")
    company_name: Optional[str] = Field(None, description="Optional company name to aid search")
    session_id: Optional[str] = Field(None, description="Optional session ID to track history")

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _is_valid_uuid4(v):
            raise ValueError("session_id must be a valid UUIDv4 string")
        return v

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's query or instruction to the agent")
    session_id: str = Field(..., description="Session identifier for message tracking")

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not _is_valid_uuid4(v):
            raise ValueError("session_id must be a valid UUIDv4 string")
        return v

class RiskFactor(BaseModel):
    category: str = Field(..., description="Category of risk (e.g., Financial, Regulatory, Operational, Competition)")
    severity: str = Field(..., description="Severity level (Low, Medium, High)")
    description: str = Field(..., description="Detailed description of the risk factor")

class RiskProfile(BaseModel):
    overall_rating: str = Field(..., description="Overall risk rating (Low, Medium, High)")
    factors: List[RiskFactor] = Field(..., description="Key risk factors identified")
    summary: str = Field(..., description="Summarized explanation of the risk profile")
    filing_url: Optional[str] = Field(None, description="URL to the SEC filing analyzed")

class NewsSentimentItem(BaseModel):
    headline: str = Field(..., description="Headline of the news article")
    source: str = Field(..., description="Source of the news article")
    date: str = Field(..., description="Publication date or relative time")
    sentiment: str = Field(..., description="Sentiment of the article (Positive, Negative, Neutral)")
    takeaway: str = Field(..., description="One-sentence key takeaway for investors")
    link: Optional[str] = Field(None, description="Direct URL link to the news article")

class SentimentAnalysis(BaseModel):
    overall_sentiment: str = Field(..., description="Overall sentiment (Bullish, Bearish, Neutral)")
    score: float = Field(..., description="Numerical sentiment score from -1.0 (extremely bearish) to 1.0 (extremely bullish)")
    items: List[NewsSentimentItem] = Field(..., description="Analyzed news headlines")

class TechnicalIndicatorValues(BaseModel):
    current_price: float = Field(..., description="Latest closing price")
    rsi_14: float = Field(..., description="14-day Relative Strength Index")
    rsi_status: str = Field(..., description="RSI status (Overbought, Oversold, Neutral)")
    macd_value: float = Field(..., description="MACD value")
    macd_signal: float = Field(..., description="MACD signal value")
    macd_status: str = Field(..., description="MACD crossover status (Bullish Cross, Bearish Cross, Neutral)")
    sma_50: float = Field(..., description="50-day Simple Moving Average")
    sma_200: float = Field(..., description="200-day Simple Moving Average")
    trend_status: str = Field(..., description="Overall technical trend (Bullish, Bearish, Sideways)")

class MacroeconomicFactors(BaseModel):
    factor_name: str = Field(..., description="Name of the macro indicator (e.g., Interest Rates, Inflation, Supply Chain)")
    impact_level: str = Field(..., description="Impact on the company (Positive, Negative, Neutral)")
    description: str = Field(..., description="Explanation of how this factor impacts the company")

class Projections(BaseModel):
    short_term: str = Field(..., description="Short-term outlook (1-3 months) projection and reasoning")
    long_term: str = Field(..., description="Long-term outlook (12+ months) projection and reasoning")

class HistoricalPricePoint(BaseModel):
    date: str = Field(..., description="Date (YYYY-MM-DD) or label for the data point")
    close: float = Field(..., description="Closing price of the stock")
    sma_50: Optional[float] = Field(None, description="50-day Simple Moving Average")
    sma_200: Optional[float] = Field(None, description="200-day Simple Moving Average")

class CompanyProfileResponse(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Full name of the company")
    generated_at: str = Field(..., description="Timestamp of when the profile was generated")
    overall_summary: str = Field(..., description="High-level investor summary synthesizing all factors")
    risk_profile: RiskProfile = Field(..., description="Aggregated corporate risk profile")
    sentiment_analysis: SentimentAnalysis = Field(..., description="Analyzed news and sentiment score")
    technical_indicators: TechnicalIndicatorValues = Field(..., description="Calculated technical indicators")
    macro_factors: List[MacroeconomicFactors] = Field(..., description="Macroeconomic headwinds and tailwinds")
    projections: Projections = Field(..., description="Short-term and long-term outlooks")
    historical_data: List[HistoricalPricePoint] = Field(default=[], description="Historical stock prices and moving averages for charting")
    forecast: Optional['ForecastData'] = Field(None, description="5-day daily price projection")

class ForecastPoint(BaseModel):
    date: str = Field(..., description="Trading date for the forecast (YYYY-MM-DD)")
    price: float = Field(..., description="Projected closing price")

class ForecastData(BaseModel):
    points: List[ForecastPoint] = Field(..., description="5-day price projection points")
    confidence_level: str = Field(..., description="Confidence rating of forecast (High, Medium, Low)")
    reasoning: str = Field(..., description="Analytical reasoning backing the forecast")

class ComparisonRequest(BaseModel):
    ticker_a: str = Field(..., description="First stock ticker symbol")
    ticker_b: str = Field(..., description="Second stock ticker symbol")

class ComparisonResponse(BaseModel):
    profile_a: CompanyProfileResponse = Field(..., description="First company analysis profile")
    profile_b: CompanyProfileResponse = Field(..., description="Second company analysis profile")
    comparative_summary: str = Field(..., description="Detailed side-by-side comparative summary by Gemini")
    comparative_risk_reward_outlook: str = Field(..., description="Gemini's relative risk-reward comparison and trade-offs. No personal buy/sell recommendation.")
    generated_at: str = Field(..., description="Timestamp of when the comparison was generated")
