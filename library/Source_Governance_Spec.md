# Blueprint: Dynamic Source Governance Engine

## 1. Database Schema Update (`ingestor.py` init_db)
Create a new table to hold source configuration and state.

```sql
CREATE TABLE IF NOT EXISTS source_registry (
    source_name TEXT PRIMARY KEY,
    feed_url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    source_type TEXT DEFAULT 'rss', -- 'rss', 'api', 'imap'
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Initialization Requirement:** On first boot, the DB must seed these initial Top-Tier frequencies if the table is empty:
- 'Google News (Dynamic)' -> 'https://news.google.com/rss' (type: rss_dynamic)
- 'SEC EDGAR Filings' -> 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=40&output=atom' (type: rss)
- 'Marketaux API' -> 'https://api.marketaux.com/v1/news/all' (type: api)
- 'Alpha Vantage' -> 'https://www.alphavantage.co/query?function=NEWS_SENTIMENT' (type: api)
- 'WhiteHouse Live' -> 'https://www.whitehouse.gov/feed/' (type: rss)

## 2. API Contract (`api.py`)
Expose the following endpoints to the React tuning console:

*   `GET /api/sources`: Returns a LEFT JOIN of `source_registry` and `source_performance` so the UI has the URL, active status, AND the total ingested/chopped/hype scores in one payload.
*   `POST /api/sources`: Accepts JSON `{ "source_name": "...", "feed_url": "...", "source_type": "..." }`. Inserts into `source_registry`.
*   `PUT /api/sources/{source_name}/toggle`: Flips `is_active` between 1 and 0.
*   `POST /api/config/targets`: Allows Trust UI to upload portfolio tickers to dynamically alter Google News and SEC queries.

## 3. Ingestor Rewiring (`ingestor.py`)
*   **Continuous Trickle:** Transition from a single loop to an async task runner or scheduler. RSS feeds can be polled every 5-10 minutes. APIs like Marketaux must be polled sparingly (e.g., every 30 mins) to preserve the 100/day free limit.
*   **Resilience:** If a source fails repeatedly, do not crash the daemon. Log the anomaly and move to the next target.