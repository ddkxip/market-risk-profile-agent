document.addEventListener('DOMContentLoaded', () => {
    // Helper to turn URLs into clickable links
    function linkify(text) {
        if (!text) return "";
        const urlRegex = /(https?:\/\/[^\s\)]+)/g;
        return text.replace(urlRegex, function(url) {
            return `<a href="${url}" target="_blank" class="fred-link" style="color: #818cf8; text-decoration: underline; font-weight: 500;">FRED Source</a>`;
        });
    }

    // Initialize Session ID
    let sessionId = localStorage.getItem('alphainsight_session_id');
    if (!sessionId) {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('alphainsight_session_id', sessionId);
    }

    // DOM Elements
    const tickerInput = document.getElementById('ticker-input');
    const tickerAInput = document.getElementById('ticker-a-input');
    const tickerBInput = document.getElementById('ticker-b-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnText = document.getElementById('btn-text');
    const welcomeScreen = document.getElementById('welcome-screen');
    const loadingScreen = document.getElementById('loading-screen');
    const loaderStatus = document.getElementById('loader-status');
    const dashboardContainer = document.getElementById('dashboard-container');
    const comparisonContainer = document.getElementById('comparison-container');
    const apiStatus = document.getElementById('api-status');
    
    const compareModeToggle = document.getElementById('compare-mode-toggle');
    const singleSearchInputs = document.getElementById('single-search-inputs');
    const compareSearchInputs = document.getElementById('compare-search-inputs');
    const modeSingleLabel = document.getElementById('mode-single');
    const modeCompareLabel = document.getElementById('mode-compare');
    const recentChipsContainer = document.getElementById('recent-chips-container');
    const suggestionChips = document.querySelectorAll('.chip');

    // State Variables
    let isCompareMode = false;
    let currentSingleData = null;
    let currentCompareData = null;

    // Toggle Single vs Compare mode
    compareModeToggle.addEventListener('change', (e) => {
        isCompareMode = e.target.checked;
        if (isCompareMode) {
            singleSearchInputs.classList.add('hidden');
            compareSearchInputs.classList.remove('hidden');
            modeSingleLabel.classList.remove('active');
            modeCompareLabel.classList.add('active');
            btnText.innerText = "Compare";
        } else {
            singleSearchInputs.classList.remove('hidden');
            compareSearchInputs.classList.add('hidden');
            modeSingleLabel.classList.add('active');
            modeCompareLabel.classList.remove('active');
            btnText.innerText = "Analyze";
        }
    });

    // Popular Tickers Suggestion Chips
    suggestionChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const ticker = chip.getAttribute('data-ticker');
            if (isCompareMode) {
                if (!tickerAInput.value) {
                    tickerAInput.value = ticker;
                } else if (!tickerBInput.value) {
                    tickerBInput.value = ticker;
                } else {
                    tickerAInput.value = ticker;
                }
            } else {
                tickerInput.value = ticker;
                triggerAnalysis(ticker);
            }
        });
    });

    // Search input enter key
    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isCompareMode) {
            const ticker = tickerInput.value.trim();
            if (ticker) triggerAnalysis(ticker);
        }
    });

    [tickerAInput, tickerBInput].forEach(inp => {
        inp.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && isCompareMode) {
                const tickA = tickerAInput.value.trim();
                const tickB = tickerBInput.value.trim();
                if (tickA && tickB) triggerComparison(tickA, tickB);
            }
        });
    });

    // Analyze button click
    analyzeBtn.addEventListener('click', () => {
        if (isCompareMode) {
            const tickA = tickerAInput.value.trim();
            const tickB = tickerBInput.value.trim();
            if (tickA && tickB) {
                triggerComparison(tickA, tickB);
            } else {
                alert("Please enter both tickers to compare.");
            }
        } else {
            const ticker = tickerInput.value.trim();
            if (ticker) {
                triggerAnalysis(ticker);
            } else {
                alert("Please enter a ticker symbol.");
            }
        }
    });

    // Manage Local Search History
    function getSearchHistory() {
        const history = localStorage.getItem('alphainsight_history');
        return history ? JSON.parse(history) : [];
    }

    function saveSearchToHistory(item) {
        let history = getSearchHistory();
        history = history.filter(x => x.toLowerCase() !== item.toLowerCase());
        history.unshift(item);
        if (history.length > 6) {
            history.pop();
        }
        localStorage.setItem('alphainsight_history', JSON.stringify(history));
        renderRecentSearches();
    }

    function renderRecentSearches() {
        const history = getSearchHistory();
        recentChipsContainer.innerHTML = '';
        
        if (history.length === 0) {
            recentChipsContainer.innerHTML = '<span class="no-history-text">No recent searches</span>';
            return;
        }
        
        history.forEach(item => {
            const chip = document.createElement('span');
            chip.className = 'chip';
            chip.innerText = item;
            
            chip.addEventListener('click', () => {
                if (item.includes(' vs ')) {
                    const tickers = item.split(' vs ');
                    tickerAInput.value = tickers[0];
                    tickerBInput.value = tickers[1];
                    compareModeToggle.checked = true;
                    compareModeToggle.dispatchEvent(new Event('change'));
                    triggerComparison(tickers[0], tickers[1]);
                } else {
                    tickerInput.value = item;
                    compareModeToggle.checked = false;
                    compareModeToggle.dispatchEvent(new Event('change'));
                    triggerAnalysis(item);
                }
            });
            
            recentChipsContainer.appendChild(chip);
        });
    }

    // Render history on load
    renderRecentSearches();

    // Loader Rotation Settings
    let loadingInterval;
    const loadingStatuses = [
        "Spawning specialized sub-agents...",
        "Market Data Agent: Downloading historical price data...",
        "Market Data Agent: Calculating RSI and MACD crossovers...",
        "SEC Agent: Mapping ticker to Central Index Key (CIK)...",
        "SEC Agent: Fetching latest 10-K from SEC EDGAR...",
        "SEC Agent: Extracting Item 1A Corporate Risk Factors...",
        "News Agent: Fetching Google News RSS search feed...",
        "News Agent: Sentiment-scoring headlines with Google Gemini...",
        "Macroeconomics Agent: Analyzing sector-specific headwinds...",
        "Coordinator Agent: Synthesizing profiles with Gemini...",
        "Finalizing investor reports..."
    ];

    function startLoadingAnimation(isComparing = false) {
        welcomeScreen.classList.add('hidden');
        dashboardContainer.classList.add('hidden');
        comparisonContainer.classList.add('hidden');
        loadingScreen.classList.remove('hidden');
        
        let statusIdx = 0;
        loaderStatus.innerText = isComparing ? "Comparing companies side-by-side..." : loadingStatuses[statusIdx];
        
        loadingInterval = setInterval(() => {
            if (isComparing) {
                loaderStatus.innerText = "Gemini is performing side-by-side comparative synthesis...";
            } else {
                statusIdx = (statusIdx + 1) % loadingStatuses.length;
                loaderStatus.innerText = loadingStatuses[statusIdx];
            }
        }, 3000);
    }

    function stopLoadingAnimation() {
        clearInterval(loadingInterval);
        loadingScreen.classList.add('hidden');
    }

    // Single Company Analysis Trigger
    async function triggerAnalysis(ticker) {
        if (!ticker) return;
        
        startLoadingAnimation(false);
        apiStatus.innerText = `Analyzing ${ticker.toUpperCase()}...`;
        
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ticker: ticker, session_id: sessionId })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error during analysis");
            }

            const data = await response.json();
            currentSingleData = data;
            populateDashboard(data);
            
            // Save search to history
            saveSearchToHistory(data.ticker);
            
            // Show single dashboard
            stopLoadingAnimation();
            dashboardContainer.classList.remove('hidden');
            apiStatus.innerText = `Idle (Analyzed ${ticker.toUpperCase()})`;
        } catch (error) {
            console.error("Error analyzing company:", error);
            stopLoadingAnimation();
            welcomeScreen.classList.remove('hidden');
            apiStatus.innerText = "Error - Check Ticker";
            alert(`Analysis failed: ${error.message}`);
        }
    }

    // Comparison Trigger
    async function triggerComparison(tickerA, tickerB) {
        if (!tickerA || !tickerB) return;
        
        startLoadingAnimation(true);
        apiStatus.innerText = `Comparing ${tickerA.toUpperCase()} vs ${tickerB.toUpperCase()}...`;
        
        try {
            const response = await fetch('/api/compare', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ticker_a: tickerA, ticker_b: tickerB })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error during comparison");
            }

            const data = await response.json();
            currentCompareData = data;
            populateComparisonDashboard(data);
            
            // Save to history
            saveSearchToHistory(`${data.profile_a.ticker} vs ${data.profile_b.ticker}`);
            
            // Show comparison dashboard
            stopLoadingAnimation();
            comparisonContainer.classList.remove('hidden');
            apiStatus.innerText = `Idle (Compared ${data.profile_a.ticker} vs ${data.profile_b.ticker})`;
        } catch (error) {
            console.error("Error comparing companies:", error);
            stopLoadingAnimation();
            welcomeScreen.classList.remove('hidden');
            apiStatus.innerText = "Error during comparison";
            alert(`Comparison failed: ${error.message}`);
        }
    }

    // Populate the Dashboard elements with Single API Data
    function populateDashboard(data) {
        // Meta
        document.getElementById('meta-company-name').innerText = data.company_name;
        document.getElementById('meta-ticker').innerText = data.ticker;
        document.getElementById('meta-timestamp').innerText = data.generated_at;
        document.getElementById('synthesis-summary').innerText = data.overall_summary;

        // Set Yahoo Finance verification link
        const yahooFinanceLink = document.getElementById('yahoo-finance-link');
        if (yahooFinanceLink) {
            yahooFinanceLink.href = `https://finance.yahoo.com/quote/${data.ticker}`;
        }

        // KPI
        document.getElementById('kpi-price').innerText = `$${data.technical_indicators.current_price.toFixed(2)}`;
        
        const sentimentVal = document.getElementById('kpi-sentiment');
        sentimentVal.innerText = data.sentiment_analysis.overall_sentiment;
        sentimentVal.className = 'kpi-value'; // Reset
        if (data.sentiment_analysis.overall_sentiment.toLowerCase().includes('bullish')) {
            sentimentVal.classList.add('sentiment-bullish');
        } else if (data.sentiment_analysis.overall_sentiment.toLowerCase().includes('bearish')) {
            sentimentVal.classList.add('sentiment-bearish');
        } else {
            sentimentVal.classList.add('sentiment-neutral');
        }
        document.getElementById('kpi-sentiment-score').innerText = data.sentiment_analysis.score.toFixed(2);

        const riskVal = document.getElementById('kpi-risk');
        riskVal.innerText = data.risk_profile.overall_rating;
        riskVal.className = 'kpi-value'; // Reset
        if (data.risk_profile.overall_rating.toLowerCase().includes('low')) {
            riskVal.classList.add('risk-low');
        } else if (data.risk_profile.overall_rating.toLowerCase().includes('medium')) {
            riskVal.classList.add('risk-medium');
        } else {
            riskVal.classList.add('risk-high');
        }

        const trendVal = document.getElementById('kpi-trend');
        trendVal.innerText = data.technical_indicators.trend_status;
        trendVal.className = 'kpi-value'; // Reset
        if (data.technical_indicators.trend_status.toLowerCase().includes('bullish')) {
            trendVal.classList.add('trend-bullish');
        } else if (data.technical_indicators.trend_status.toLowerCase().includes('bearish')) {
            trendVal.classList.add('trend-bearish');
        } else {
            trendVal.classList.add('sentiment-neutral');
        }

        // Technicals List
        document.getElementById('tech-rsi').innerText = `${data.technical_indicators.rsi_14.toFixed(1)} (${data.technical_indicators.rsi_status})`;
        document.getElementById('tech-macd').innerText = data.technical_indicators.macd_status;
        document.getElementById('tech-sma50').innerText = `$${data.technical_indicators.sma_50.toFixed(2)}`;
        document.getElementById('tech-sma200').innerText = `$${data.technical_indicators.sma_200.toFixed(2)}`;

        // SEC Summary & Factors
        document.getElementById('sec-risk-summary').innerText = data.risk_profile.summary;
        
        // Set SEC Filing link
        const secFilingLink = document.getElementById('sec-filing-link');
        if (secFilingLink && data.risk_profile.filing_url) {
            secFilingLink.href = data.risk_profile.filing_url;
            secFilingLink.classList.remove('hidden');
        } else if (secFilingLink) {
            secFilingLink.classList.add('hidden');
        }

        const secContainer = document.getElementById('sec-factors-container');
        secContainer.innerHTML = '';
        
        data.risk_profile.factors.forEach(factor => {
            const card = document.createElement('div');
            card.className = 'sec-factor-card';
            
            const sevClass = factor.severity.toLowerCase().includes('high') ? 'severity-high' : 
                             (factor.severity.toLowerCase().includes('medium') ? 'severity-medium' : 'severity-low');
                             
            card.innerHTML = `
                <div class="sec-factor-header">
                    <h4>${factor.category}</h4>
                    <span class="severity-badge ${sevClass}">${factor.severity}</span>
                </div>
                <p>${factor.description}</p>
            `;
            secContainer.appendChild(card);
        });

        // News headlines
        const newsContainer = document.getElementById('news-headlines-container');
        newsContainer.innerHTML = '';
        
        if (data.sentiment_analysis.items && data.sentiment_analysis.items.length > 0) {
            data.sentiment_analysis.items.forEach(item => {
                const newsItem = document.createElement('div');
                newsItem.className = 'news-item';
                
                const sentColor = item.sentiment.toLowerCase().includes('positive') ? 'sentiment-bullish' :
                                  (item.sentiment.toLowerCase().includes('negative') ? 'sentiment-bearish' : 'sentiment-neutral');
                
                const headlineHtml = item.link 
                    ? `<a href="${item.link}" target="_blank" class="news-item-title-link">${item.headline}</a>` 
                    : item.headline;

                newsItem.innerHTML = `
                    <div class="news-meta">
                        <span>${item.source} • ${item.date}</span>
                        <span class="impact-badge ${sentColor}">${item.sentiment}</span>
                    </div>
                    <h4>${headlineHtml}</h4>
                    <div class="news-takeaway">
                        <strong>Takeaway:</strong> ${item.takeaway}
                    </div>
                `;
                newsContainer.appendChild(newsItem);
            });
        } else {
            newsContainer.innerHTML = '<p class="text-muted">No recent news headlines analyzed.</p>';
        }

        // Macro factors
        const macroContainer = document.getElementById('macro-factors-container');
        macroContainer.innerHTML = '';
        
        data.macro_factors.forEach(factor => {
            const macroItem = document.createElement('div');
            const impactClass = factor.impact_level.toLowerCase().includes('positive') ? 'impact-positive' : 
                               (factor.impact_level.toLowerCase().includes('negative') ? 'impact-negative' : 'impact-neutral');
                               
            macroItem.className = `macro-item ${impactClass}`;
            macroItem.innerHTML = `
                <div class="macro-item-header">
                    <h4>${factor.factor_name}</h4>
                    <span class="impact-badge">${factor.impact_level}</span>
                </div>
                <p>${linkify(factor.description)}</p>
            `;
            macroContainer.appendChild(macroItem);
        });

        // Projections
        document.getElementById('proj-short').innerText = data.projections.short_term;
        document.getElementById('proj-long').innerText = data.projections.long_term;

        // Render AI 5-Day Price Forecast
        const forecastConfidence = document.getElementById('forecast-confidence');
        const forecastValuesList = document.getElementById('forecast-values-list');
        const forecastReasoning = document.getElementById('forecast-reasoning');
        
        if (data.forecast) {
            forecastConfidence.innerText = `Confidence: ${data.forecast.confidence_level}`;
            forecastConfidence.className = 'badge';
            if (data.forecast.confidence_level.toLowerCase() === 'high') {
                forecastConfidence.style.backgroundColor = 'rgba(34, 197, 94, 0.1)';
                forecastConfidence.style.color = '#22c55e';
            } else if (data.forecast.confidence_level.toLowerCase() === 'medium') {
                forecastConfidence.style.backgroundColor = 'rgba(234, 179, 8, 0.1)';
                forecastConfidence.style.color = '#eab308';
            } else {
                forecastConfidence.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                forecastConfidence.style.color = '#ef4444';
            }

            forecastValuesList.innerHTML = '';
            data.forecast.points.forEach(pt => {
                const row = document.createElement('div');
                row.className = 'indicator-row';
                row.innerHTML = `
                    <span>${pt.date}</span>
                    <span style="font-weight: 700; color: #ffffff;">$${pt.price.toFixed(2)}</span>
                `;
                forecastValuesList.appendChild(row);
            });
            forecastReasoning.innerText = data.forecast.reasoning;
        } else {
            forecastConfidence.innerText = 'Confidence: N/A';
            forecastValuesList.innerHTML = '<span class="text-muted">No forecast data generated.</span>';
            forecastReasoning.innerText = '';
        }

        // Render Apex Chart
        priceChartInstance = renderSingleChart(
            "price-chart", 
            data.historical_data, 
            data.technical_indicators, 
            ['#6366f1', '#10b981', '#f59e0b'], 
            priceChartInstance
        );
    }

    // Populate Comparison Dashboard
    function populateComparisonDashboard(data) {
        const profileA = data.profile_a;
        const profileB = data.profile_b;
        
        // Metadata & Headers
        document.getElementById('compare-badge-a').innerText = profileA.ticker;
        document.getElementById('compare-badge-b').innerText = profileB.ticker;
        document.getElementById('compare-timestamp').innerText = data.generated_at;
        document.getElementById('compare-summary').innerText = data.comparative_summary;
        document.getElementById('compare-recommendation').innerText = data.better_investment;
        
        // Table Headers Labels
        document.getElementById('comp-label-a').innerText = profileA.ticker;
        document.getElementById('comp-label-b').innerText = profileB.ticker;
        document.getElementById('comp-label-a2').innerText = profileA.ticker;
        document.getElementById('comp-label-b2').innerText = profileB.ticker;
        
        // Prices & indicators
        document.getElementById('comp-price-a').innerText = `$${profileA.technical_indicators.current_price.toFixed(2)}`;
        document.getElementById('comp-price-b').innerText = `$${profileB.technical_indicators.current_price.toFixed(2)}`;
        
        // Technical trends
        const trendA = document.getElementById('comp-trend-a');
        trendA.innerText = profileA.technical_indicators.trend_status;
        trendA.className = profileA.technical_indicators.trend_status.toLowerCase().includes('bullish') ? 'trend-bullish' : 
                         (profileA.technical_indicators.trend_status.toLowerCase().includes('bearish') ? 'trend-bearish' : '');
                         
        const trendB = document.getElementById('comp-trend-b');
        trendB.innerText = profileB.technical_indicators.trend_status;
        trendB.className = profileB.technical_indicators.trend_status.toLowerCase().includes('bullish') ? 'trend-bullish' : 
                         (profileB.technical_indicators.trend_status.toLowerCase().includes('bearish') ? 'trend-bearish' : '');
        
        // RSI
        document.getElementById('comp-rsi-a').innerText = `${profileA.technical_indicators.rsi_14.toFixed(1)} (${profileA.technical_indicators.rsi_status})`;
        document.getElementById('comp-rsi-b').innerText = `${profileB.technical_indicators.rsi_14.toFixed(1)} (${profileB.technical_indicators.rsi_status})`;
        
        // MACD
        document.getElementById('comp-macd-a').innerText = profileA.technical_indicators.macd_status;
        document.getElementById('comp-macd-b').innerText = profileB.technical_indicators.macd_status;
        
        // SMAs
        document.getElementById('comp-sma50-a').innerText = `$${profileA.technical_indicators.sma_50.toFixed(2)}`;
        document.getElementById('comp-sma50-b').innerText = `$${profileB.technical_indicators.sma_50.toFixed(2)}`;
        document.getElementById('comp-sma200-a').innerText = `$${profileA.technical_indicators.sma_200.toFixed(2)}`;
        document.getElementById('comp-sma200-b').innerText = `$${profileB.technical_indicators.sma_200.toFixed(2)}`;
        
        // Risk levels
        const riskRatingA = document.getElementById('comp-risk-rating-a');
        riskRatingA.innerText = profileA.risk_profile.overall_rating;
        riskRatingA.className = profileA.risk_profile.overall_rating.toLowerCase().includes('low') ? 'risk-low' : 
                               (profileA.risk_profile.overall_rating.toLowerCase().includes('medium') ? 'risk-medium' : 'risk-high');
                               
        const riskRatingB = document.getElementById('comp-risk-rating-b');
        riskRatingB.innerText = profileB.risk_profile.overall_rating;
        riskRatingB.className = profileB.risk_profile.overall_rating.toLowerCase().includes('low') ? 'risk-low' : 
                               (profileB.risk_profile.overall_rating.toLowerCase().includes('medium') ? 'risk-medium' : 'risk-high');
                               
        // Sentiment
        const sentA = document.getElementById('comp-sentiment-a');
        sentA.innerText = profileA.sentiment_analysis.overall_sentiment;
        sentA.className = profileA.sentiment_analysis.overall_sentiment.toLowerCase().includes('bullish') ? 'sentiment-bullish' : 
                         (profileA.sentiment_analysis.overall_sentiment.toLowerCase().includes('bearish') ? 'sentiment-bearish' : 'sentiment-neutral');
                         
        const sentB = document.getElementById('comp-sentiment-b');
        sentB.innerText = profileB.sentiment_analysis.overall_sentiment;
        sentB.className = profileB.sentiment_analysis.overall_sentiment.toLowerCase().includes('bullish') ? 'sentiment-bullish' : 
                         (profileB.sentiment_analysis.overall_sentiment.toLowerCase().includes('bearish') ? 'sentiment-bearish' : 'sentiment-neutral');
                         
        document.getElementById('comp-sent-score-a').innerText = profileA.sentiment_analysis.score.toFixed(2);
        document.getElementById('comp-sent-score-b').innerText = profileB.sentiment_analysis.score.toFixed(2);
        
        // SEC sources
        const secLinkA = document.getElementById('comp-sec-a');
        if (profileA.risk_profile.filing_url) {
            secLinkA.href = profileA.risk_profile.filing_url;
            secLinkA.style.display = 'inline-flex';
        } else {
            secLinkA.style.display = 'none';
        }
        
        const secLinkB = document.getElementById('comp-sec-b');
        if (profileB.risk_profile.filing_url) {
            secLinkB.href = profileB.risk_profile.filing_url;
            secLinkB.style.display = 'inline-flex';
        } else {
            secLinkB.style.display = 'none';
        }

        // Render News side-by-side
        document.getElementById('news-title-a').innerText = `${profileA.company_name} News`;
        const newsContainerA = document.getElementById('compare-news-a');
        populateComparisonNewsColumn(newsContainerA, profileA.sentiment_analysis.items);

        document.getElementById('news-title-b').innerText = `${profileB.company_name} News`;
        const newsContainerB = document.getElementById('compare-news-b');
        populateComparisonNewsColumn(newsContainerB, profileB.sentiment_analysis.items);

        // Render Charts side-by-side
        renderComparisonCharts(data);
    }

    // Populate comparison news column
    function populateComparisonNewsColumn(container, items) {
        container.innerHTML = '';
        if (items && items.length > 0) {
            items.forEach(item => {
                const newsItem = document.createElement('div');
                newsItem.className = 'news-item';
                
                const sentColor = item.sentiment.toLowerCase().includes('positive') ? 'sentiment-bullish' :
                                  (item.sentiment.toLowerCase().includes('negative') ? 'sentiment-bearish' : 'sentiment-neutral');
                
                const headlineHtml = item.link 
                    ? `<a href="${item.link}" target="_blank" class="news-item-title-link" style="font-size: 0.9rem;">${item.headline}</a>` 
                    : `<span style="font-size: 0.9rem;">${item.headline}</span>`;

                newsItem.innerHTML = `
                    <div class="news-meta" style="margin-bottom: 0.25rem;">
                        <span style="font-size: 0.75rem;">${item.source} • ${item.date}</span>
                        <span class="impact-badge ${sentColor}" style="padding: 0.15rem 0.4rem; font-size: 0.7rem;">${item.sentiment}</span>
                    </div>
                    <h4 style="font-size: 0.9rem; margin-bottom: 0.25rem;">${headlineHtml}</h4>
                    <div class="news-takeaway" style="font-size: 0.8rem; padding: 0.4rem; border-radius: 6px; background: rgba(255,255,255,0.02);">
                        <strong>Takeaway:</strong> ${item.takeaway}
                    </div>
                `;
                container.appendChild(newsItem);
            });
        } else {
            container.innerHTML = '<p class="text-muted" style="font-size: 0.85rem;">No recent news headlines available.</p>';
        }
    }

    // Render comparison charts
    let compareChartAInstance = null;
    let compareChartBInstance = null;

    function renderComparisonCharts(data) {
        const profileA = data.profile_a;
        const profileB = data.profile_b;
        
        document.getElementById('chart-title-a').innerText = `${profileA.company_name} Price Trend`;
        document.getElementById('chart-title-b').innerText = `${profileB.company_name} Price Trend`;
        
        compareChartAInstance = renderSingleChart(
            "compare-chart-a", 
            profileA.historical_data, 
            profileA.technical_indicators, 
            ['#6366f1', '#10b981', '#f59e0b'],
            compareChartAInstance
        );
        
        compareChartBInstance = renderSingleChart(
            "compare-chart-b", 
            profileB.historical_data, 
            profileB.technical_indicators, 
            ['#a855f7', '#10b981', '#f59e0b'],
            compareChartBInstance
        );
    }



    // Markdown Exporter Fallbacks
    function exportSingleReport(data) {
        let md = `# Investment & Risk Report: ${data.company_name} (${data.ticker})\n`;
        md += `Generated on: ${data.generated_at}\n\n`;
        md += `## 1. Executive Summary\n${data.overall_summary}\n\n`;
        md += `## 2. Technical Profile\n`;
        md += `- **Current Price**: $${data.technical_indicators.current_price}\n`;
        md += `- **Technical Trend**: ${data.technical_indicators.trend_status}\n`;
        md += `- **RSI (14)**: ${data.technical_indicators.rsi_14} (${data.technical_indicators.rsi_status})\n`;
        md += `- **MACD**: ${data.technical_indicators.macd_value} (Status: ${data.technical_indicators.macd_status})\n`;
        md += `- **50 SMA**: $${data.technical_indicators.sma_50}\n`;
        md += `- **200 SMA**: $${data.technical_indicators.sma_200}\n\n`;
        md += `## 3. Corporate Risk Factors\n`;
        md += `**Overall Risk Rating**: ${data.risk_profile.overall_rating}\n\n`;
        md += `**Summary**: ${data.risk_profile.summary}\n\n`;
        data.risk_profile.factors.forEach(factor => {
            md += `### [${factor.category} | Severity: ${factor.severity}]\n${factor.description}\n\n`;
        });
        md += `## 4. News & Sentiment Analysis\n`;
        md += `- **Overall Sentiment**: ${data.sentiment_analysis.overall_sentiment}\n`;
        md += `- **Sentiment Score**: ${data.sentiment_analysis.score} (-1.0 to 1.0)\n\n`;
        data.sentiment_analysis.items.forEach(item => {
            md += `- **${item.headline}** (${item.source} • ${item.date})\n`;
            md += `  *Takeaway*: ${item.takeaway}\n\n`;
        });
        md += `## 5. Macroeconomic Influences\n`;
        data.macro_factors.forEach(factor => {
            md += `- **${factor.factor_name}** (Impact: ${factor.impact_level})\n  ${factor.description}\n\n`;
        });
        md += `## 6. Projections & Outlook\n`;
        md += `### Short-Term Outlook (1-3 Months)\n${data.projections.short_term}\n\n`;
        md += `### Long-Term Outlook (12+ Months)\n${data.projections.long_term}\n\n`;
        
        triggerFileDownload(`${data.ticker}_investment_report.md`, md);
    }

    function exportComparisonReport(data) {
        const profileA = data.profile_a;
        const profileB = data.profile_b;
        
        let md = `# Comparative Investment Report: ${profileA.ticker} vs ${profileB.ticker}\n`;
        md += `Generated on: ${data.generated_at}\n\n`;
        md += `## 1. Gemini Comparison Summary\n${data.comparative_summary}\n\n`;
        md += `## 2. Investment Recommendation\n${data.better_investment}\n\n`;
        md += `| Metric | ${profileA.ticker} | ${profileB.ticker} |\n`;
        md += `| --- | --- | --- |\n`;
        md += `| **Company Name** | ${profileA.company_name} | ${profileB.company_name} |\n`;
        md += `| **Current Price** | $${profileA.technical_indicators.current_price} | $${profileB.technical_indicators.current_price} |\n`;
        md += `| **Overall Risk Rating** | ${profileA.risk_profile.overall_rating} | ${profileB.risk_profile.overall_rating} |\n`;
        md += `| **Sentiment Score** | ${profileA.sentiment_analysis.score} | ${profileB.sentiment_analysis.score} |\n`;
        
        triggerFileDownload(`${profileA.ticker}_vs_${profileB.ticker}_comparison_report.md`, md);
    }

    function triggerFileDownload(filename, text) {
        const element = document.createElement('a');
        element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
        element.setAttribute('download', filename);
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    }

    // Export button events
    document.getElementById('export-report-md-btn').addEventListener('click', () => {
        exportSingleReport(currentSingleData);
    });

    document.getElementById('export-comparison-md-btn').addEventListener('click', () => {
        exportComparisonReport(currentCompareData);
    });

    // Unified Charting Function
    let priceChartInstance = null;
    function renderSingleChart(elementId, historicalData, technicals, colors, existingInstance) {
        const dates = [];
        const prices = [];
        const sma50Series = [];
        const sma200Series = [];
        
        if (historicalData && historicalData.length > 0) {
            historicalData.forEach(point => {
                const parts = point.date.split('-');
                let dateLabel = point.date;
                if (parts.length === 3) {
                    const dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
                    dateLabel = dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                }
                dates.push(dateLabel);
                prices.push(point.close);
                sma50Series.push(point.sma_50);
                sma200Series.push(point.sma_200);
            });
        } else {
            const currentPrice = technicals.current_price;
            const sma50 = technicals.sma_50;
            const sma200 = technicals.sma_200;
            const now = new Date();
            for (let i = 29; i >= 0; i--) {
                const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
                dates.push(date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
                
                const ratio = (30 - i) / 30;
                const simulatedPrice = sma200 + (currentPrice - sma200) * ratio + (Math.sin(i / 2) * (currentPrice * 0.02));
                prices.push(parseFloat(simulatedPrice.toFixed(2)));
                
                const simulatedSma50 = sma200 + (sma50 - sma200) * ratio;
                sma50Series.push(parseFloat(simulatedSma50.toFixed(2)));
                sma200Series.push(parseFloat(sma200.toFixed(2)));
            }
        }

        const options = {
            series: [
                {
                    name: 'Stock Price',
                    type: 'area',
                    data: prices
                },
                {
                    name: '50 SMA',
                    type: 'line',
                    data: sma50Series
                },
                {
                    name: '200 SMA',
                    type: 'line',
                    data: sma200Series
                }
            ],
            chart: {
                height: 200,
                type: 'line',
                background: 'transparent',
                toolbar: {
                    show: false
                }
            },
            colors: colors,
            fill: {
                type: 'solid',
                opacity: [0.1, 1, 1],
            },
            stroke: {
                width: [3, 2, 2],
                curve: 'smooth'
            },
            xaxis: {
                categories: dates,
                labels: {
                    style: {
                        colors: '#64748b'
                    }
                },
                axisBorder: {
                    show: false
                },
                axisTicks: {
                    show: false
                }
            },
            yaxis: {
                labels: {
                    style: {
                        colors: '#64748b'
                    },
                    formatter: function (val) {
                        return "$" + val.toFixed(0);
                    }
                }
            },
            tooltip: {
                theme: 'dark',
                shared: true
            },
            grid: {
                borderColor: 'rgba(255, 255, 255, 0.04)',
                strokeDashArray: 4
            },
            legend: {
                labels: {
                    colors: '#94a3b8'
                }
            }
        };

        const chartElement = document.getElementById(elementId);
        
        if (existingInstance) {
            existingInstance.destroy();
        }
        
        chartElement.innerHTML = '';
        const chartInstance = new ApexCharts(chartElement, options);
        chartInstance.render();
        return chartInstance;
    }

    // --- Chatbot Drawer Controller ---
    const chatbotDrawer = document.getElementById('chatbot-drawer');
    const chatbotHeader = document.getElementById('chatbot-header');
    const toggleChatBtn = document.getElementById('toggle-chat-btn');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const clearChatBtn = document.getElementById('clear-chat-btn');

    // Toggle Chat Panel Expand/Collapse
    chatbotHeader.addEventListener('click', (e) => {
        // Prevent click trigger if clear button is clicked
        if (e.target.closest('#clear-chat-btn')) return;
        
        chatbotDrawer.classList.toggle('collapsed');
        const isCollapsed = chatbotDrawer.classList.contains('collapsed');
        toggleChatBtn.innerHTML = isCollapsed ? '<i class="fa-solid fa-chevron-up"></i>' : '<i class="fa-solid fa-chevron-down"></i>';
        
        if (!isCollapsed) {
            chatInput.focus();
            scrollChatToBottom();
        }
    });

    // Scroll Chat to Bottom
    function scrollChatToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Render Chat History from Database
    function renderChatHistory(history) {
        // Clear except first welcome message
        const welcomeMessage = chatMessages.firstElementChild.outerHTML;
        chatMessages.innerHTML = welcomeMessage;
        
        history.forEach(msg => {
            appendChatBubble(msg.role, msg.content, false);
        });
        scrollChatToBottom();
    }

    // Append Chat Bubble
    function appendChatBubble(role, text, shouldScroll = true) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${role}`;
        
        const paragraphs = text.split('\n').filter(p => p.trim());
        bubble.innerHTML = paragraphs.map(p => `<p>${escapeHTML(p)}</p>`).join('');
        
        chatMessages.appendChild(bubble);
        if (shouldScroll) {
            scrollChatToBottom();
        }
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }

    // Load Chat History from Server on Boot
    async function loadSessionHistory() {
        try {
            const res = await fetch(`/api/chat/history/${sessionId}`);
            if (res.ok) {
                const data = await res.json();
                if (data.history && data.history.length > 0) {
                    renderChatHistory(data.history);
                }
            }
        } catch (err) {
            console.error("Failed to load chat history:", err);
        }
    }

    // Clear Chat History
    clearChatBtn.addEventListener('click', async () => {
        if (confirm("Are you sure you want to clear this chat session?")) {
            try {
                const res = await fetch(`/api/chat/history/${sessionId}`, { method: 'DELETE' });
                if (res.ok) {
                    const welcomeMessage = chatMessages.firstElementChild.outerHTML;
                    chatMessages.innerHTML = welcomeMessage;
                }
            } catch (err) {
                console.error("Failed to clear history:", err);
            }
        }
    });

    // Send Message to Agent
    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;
        
        chatInput.value = '';
        appendChatBubble('user', message);
        
        // Disable input
        chatInput.disabled = true;
        chatSendBtn.disabled = true;
        
        // Show typing indicator bubble
        const typingBubble = document.createElement('div');
        typingBubble.className = 'chat-bubble model typing-indicator';
        typingBubble.innerHTML = '<p>Copilot thinking...</p>';
        chatMessages.appendChild(typingBubble);
        scrollChatToBottom();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message, session_id: sessionId })
            });

            // Remove typing bubble
            typingBubble.remove();

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Server error");
            }

            const data = await res.json();
            appendChatBubble('model', data.reply);

        } catch (error) {
            console.error("Chat error:", error);
            typingBubble.remove();
            appendChatBubble('system', `Error sending message: ${error.message}`);
        } finally {
            chatInput.disabled = false;
            chatSendBtn.disabled = false;
            chatInput.focus();
        }
    }

    chatSendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Boot execution
    loadSessionHistory();
});
