import os
import datetime
import finnhub
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Initialize APIs
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
analyzer = SentimentIntensityAnalyzer()

# Watchlist of major US market movers (expand as needed)
WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "UNH", "XOM"]

# High-impact financial catalyst weights
CATALYST_WEIGHTS = {
    "downgrade": 4.0, "upgrade": 4.0, "price target": 3.0,
    "earnings": 3.5, "guidance": 3.5, "fed": 4.0, "interest rate": 4.0,
    "inflation": 3.5, "cpi": 3.5, "merger": 4.5, "acquisition": 4.5,
    "sec": 3.5, "lawsuit": 3.0, "fda": 4.5, "bankruptcy": 5.0,
    "layoffs": 2.5, "dividend": 2.5, "buyback": 2.5
}

def calculate_impact_score(headline: str, summary: str, is_rating_change: bool = False) -> tuple[float, str]:
    """Ranks news from 1 to 10 based on catalyst keywords and sentiment polarity."""
    text = f"{headline} {summary}".lower()
    sentiment = analyzer.polarity_scores(text)["compound"]
    
    # Base score from sentiment intensity (0 to 3 points)
    score = abs(sentiment) * 3.0
    
    # Add catalyst weight
    matched_catalysts = []
    for keyword, weight in CATALYST_WEIGHTS.items():
        if keyword in text:
            score += weight
            matched_catalysts.append(keyword.upper())
            
    if is_rating_change:
        score += 3.5
        
    final_score = min(round(score, 2), 10.0)
    direction = "🟢 BULLISH" if sentiment >= 0.15 else ("🔴 BEARISH" if sentiment <= -0.15 else "⚪ NEUTRAL")
    return final_score, direction

def fetch_market_news():
    """Fetches top US general & financial news from Finnhub."""
    raw_news = finnhub_client.general_news("general", min_id=0)[:40]
    processed = []
    for item in raw_news:
        headline = item.get("headline", "")
        summary = item.get("summary", "")
        score, direction = calculate_impact_score(headline, summary)
        processed.append({
            "type": "Market News",
            "ticker": "MARKET",
            "title": headline,
            "source": item.get("source", "Unknown"),
            "url": item.get("url", ""),
            "score": score,
            "direction": direction
        })
    return processed

def fetch_upgrades_downgrades():
    """Fetches recent analyst rating upgrades/downgrades for watchlist tickers."""
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    ratings_events = []

    for ticker in WATCHLIST:
        try:
            # Pull upgrades/downgrades via yfinance
            stock = yf.Ticker(ticker)
            df = stock.upgrades_downgrades
            if df is not None and not df.empty:
                recent = df[df.index >= str(yesterday)]
                for date_idx, row in recent.iterrows():
                    firm = row.get("Firm", "Analyst")
                    action = row.get("Action", "Rating Change")
                    from_grade = row.get("FromGrade", "N/A")
                    to_grade = row.get("ToGrade", "N/A")
                    
                    headline = f"[{ticker}] {firm} {action}: {from_grade} -> {to_grade}"
                    score, direction = calculate_impact_score(headline, action, is_rating_change=True)
                    
                    # Override direction explicitly for upgrades/downgrades
                    if "up" in action.lower():
                        direction = "🟢 BULLISH (UPGRADE)"
                    elif "down" in action.lower():
                        direction = "🔴 BEARISH (DOWNGRADE)"
                        
                    ratings_events.append({
                        "type": "Analyst Rating",
                        "ticker": ticker,
                        "title": headline,
                        "source": firm,
                        "url": f"https://finance.yahoo.com/quote/{ticker}/analysis",
                        "score": score,
                        "direction": direction
                    })
        except Exception as e:
            print(f"Skipping {ticker} ratings: {e}")
            
    return ratings_events

def generate_markdown_report(items: list):
    """Sorts all items by impact score and writes a Markdown report."""
    ranked = sorted(items, key=lambda x: x["score"], reverse=True)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    session = "PRE-MARKET (08:30 EST)" if now_utc.hour < 16 else "PRE-CLOSE (15:30 EST)"
    date_str = now_utc.strftime("%Y-%m-%d")
    
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/{date_str}_{'pre-market' if now_utc.hour < 16 else 'pre-close'}.md"
    
    lines = [
        f"# 🇺🇸 US Stock Market & Financial Impact Report",
        f"**Date:** {date_str} | **Session:** {session} | **Generated:** {now_utc.strftime('%H:%M UTC')}\n",
        "## 🔥 Top Market-Moving Events (Ranked by Price Impact)\n",
        "| Rank | Impact Score | Signal | Ticker | Category | Headline / Action |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for idx, item in enumerate(ranked[:25], start=1):
        clean_title = item["title"].replace("|", "-")
        link = f"[{clean_title}]({item['url']})" if item["url"] else clean_title
        lines.append(
            f"| #{idx} | **{item['score']}/10** | {item['direction']} | `{item['ticker']}` | {item['type']} | {link} |"
        )
        
    report_content = "\n".join(lines)
    
    # Save timestamped archive report AND overwrite README.md for instant viewing
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_content)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    news_items = fetch_market_news()
    rating_items = fetch_upgrades_downgrades()
    generate_markdown_report(news_items + rating_items)
