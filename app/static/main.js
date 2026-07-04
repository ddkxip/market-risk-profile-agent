document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const tickerInput = document.getElementById('ticker-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const welcomeScreen = document.getElementById('welcome-screen');
    const loadingScreen = document.getElementById('loading-screen');
    const loaderStatus = document.getElementById('loader-status');
    const dashboardContainer = document.getElementById('dashboard-container');
    const apiStatus = document.getElementById('api-status');
    const suggestionChips = document.querySelectorAll('.chip');

    // Popular Tickers Suggestion Chips
    suggestionChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const ticker = chip.getAttribute('data-ticker');
            tickerInput.value = ticker;
            triggerAnalysis(ticker);
        });
    });

    // Search input enter key
    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const ticker = tickerInput.value.trim();
            if (ticker) triggerAnalysis(ticker);
        }
    });

    // Analyze button click
    analyzeBtn.addEventListener('click', () => {
        const ticker = tickerInput.value.trim();
        if (ticker) triggerAnalysis(ticker);
    });

    // Status rotation during load
    let loadingInterval;
    const loadingStatuses = [
        "Spawning specialized sub-agents...",
        "Market Data Agent: Downloading historical price data...",
        "Market Data Agent: Calculating RSI and MACD crossovers...",
        "SEC Agent: Mapping ticker to Central Index Key (CIK)...",
        "SEC Agent: Fetching latest 10-K from SEC EDGAR...",
        "SEC Agent: Extracting Item 1A Corporate Risk Factors...",
        "News Agent: Fetching Google & Yahoo Finance headlines...",
        "News Agent: Sentiment-scoring headlines with Google Gemini...",
        "Macroeconomics Agent: Analyzing interest rate and inflation impact...",
        "Coordinator Agent: Synthesizing profiles with Gemini 2.5 Flash...",
        "Finalizing investor rating and short-to-long term outlook..."
    ];

    function startLoadingAnimation() {
        welcomeScreen.classList.add('hidden');
        dashboardContainer.classList.add('hidden');
        loadingScreen.classList.remove('hidden');
        
        let statusIdx = 0;
        loaderStatus.innerText = loadingStatuses[statusIdx];
        
        loadingInterval = setInterval(() => {
            statusIdx = (statusIdx + 1) % loadingStatuses.length;
            loaderStatus.innerText = loadingStatuses[statusIdx];
        }, 3000);
    }

    function stopLoadingAnimation() {
        clearInterval(loadingInterval);
        loadingScreen.classList.add('hidden');
    }

    // Main Analysis Trigger
    async function triggerAnalysis(ticker) {
        if (!ticker) return;
        
        startLoadingAnimation();
        apiStatus.innerText = `Analyzing ${ticker.toUpperCase()}...`;
        
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ticker: ticker })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error during analysis");
            }

            const data = await response.json();
            populateDashboard(data);
            
            // Show dashboard
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

    // Populate the Dashboard elements with API Data
    function populateDashboard(data) {
        // Meta
        document.getElementById('meta-company-name').innerText = data.company_name;
        document.getElementById('meta-ticker').innerText = data.ticker;
        document.getElementById('meta-timestamp').innerText = data.generated_at;
        document.getElementById('synthesis-summary').innerText = data.overall_summary;

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
                
                newsItem.innerHTML = `
                    <div class="news-meta">
                        <span>${item.source} • ${item.date}</span>
                        <span class="impact-badge ${sentColor}">${item.sentiment}</span>
                    </div>
                    <h4>${item.headline}</h4>
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
                <p>${factor.description}</p>
            `;
            macroContainer.appendChild(macroItem);
        });

        // Projections
        document.getElementById('proj-short').innerText = data.projections.short_term;
        document.getElementById('proj-long').innerText = data.projections.long_term;

        // Render Apex Chart
        renderPriceChart(data.technical_indicators);
    }

    // Render stock technical chart
    let priceChartInstance = null;
    function renderPriceChart(technicals) {
        const currentPrice = technicals.current_price;
        const sma50 = technicals.sma_50;
        const sma200 = technicals.sma_200;
        
        // Generate simulated price points over 30 days to visualize SMA trends ending at current levels
        const dates = [];
        const prices = [];
        const sma50Series = [];
        const sma200Series = [];
        
        const now = new Date();
        for (let i = 29; i >= 0; i--) {
            const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
            dates.push(date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
            
            // Build progressive chart curves merging into the final outputs
            const ratio = (30 - i) / 30;
            const simulatedPrice = sma200 + (currentPrice - sma200) * ratio + (Math.sin(i / 2) * (currentPrice * 0.02));
            prices.push(parseFloat(simulatedPrice.toFixed(2)));
            
            const simulatedSma50 = sma200 + (sma50 - sma200) * ratio;
            sma50Series.push(parseFloat(simulatedSma50.toFixed(2)));
            sma200Series.push(parseFloat(sma200.toFixed(2)));
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
                height: 220,
                type: 'line',
                background: 'transparent',
                toolbar: {
                    show: false
                }
            },
            colors: ['#6366f1', '#10b981', '#f59e0b'],
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

        const chartElement = document.getElementById("price-chart");
        
        // Destroy existing chart if it exists
        if (priceChartInstance) {
            priceChartInstance.destroy();
        }
        
        chartElement.innerHTML = '';
        priceChartInstance = new ApexCharts(chartElement, options);
        priceChartInstance.render();
    }
});
