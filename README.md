# Market Risk & Trading Profile Copilot

An AI-agent-powered system designed for the **5-Day AI Agents Intensive: Vibe Coding Course with Google** Capstone Project.

This copilot aggregates data from open-source and public APIs to build a multi-dimensional risk and trading profile for publicly traded US companies (focusing on NASDAQ 100/S&P 500).

## Core Features
1. **SEC Documents Agent**: Downloads and reviews recent SEC filings (10-K, 10-Q) to extract corporate risk factors.
2. **News & Sentiment Agent**: Gathers recent headlines and performs sentiment analysis using Google Gemini.
3. **Market Data & Technicals Agent**: Pulls stock price data and calculates technical indicators (RSI, MACD, Moving Averages).
4. **Macroeconomics Agent**: Summarizes macroeconomic headwinds/tailwinds affecting the target sector.
5. **Synthesis Engine**: Orchestrates the agents to construct short-term/long-term projections and an overall investor risk rating.

## Tech Stack
- **Backend**: Python (FastAPI), Google GenAI SDK (Gemini)
- **Frontend**: Vanilla HTML5, CSS3, Javascript (ApexCharts, html2pdf.js)

## Getting Started
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   python -m app.main
   ```
3. Access the web dashboard at `http://127.0.0.1:8000/`.
