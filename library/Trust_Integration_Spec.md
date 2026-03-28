# Trust & Intelligence: Integration API Contract

## 1. Architectural Philosophy
*   **Dumb Client, Smart Server:** The `Trust` module (React UI) is strictly for rendering. It performs zero news scraping, deduplication, or AI inference.
*   **Autonomous Daemon:** The `Intelligence` module handles its own background polling. It continuously updates its local SQLite/ChromaDB matrix.
*   **Read-Only UI:** Trust fetches pre-compiled JSON. It never waits for AI generation.

## 2. Base Configuration
*   **Intelligence API Base URL:** `http://localhost:8001`
*   **CORS:** Configured to accept requests from Trust's local dev server (`http://localhost:5173`).

## 3. Data Flow Contract

### A. What Intelligence Passes to Trust (The Output)

**1. The Daily Briefing**
*   **Endpoint:** `GET /api/briefing/latest?limit=50`
*   **Purpose:** The core news feed for the Trust UI.
*   **Payload Returns:**
    ```json
    {
      "briefings": [
        {
          "id": 102,
          "title": "Apple Announces M4 Chip",
          "dehyped_summary": "Apple has released the M4 processor with a focus on neural engine performance.",
          "current_facts": ["M4 chip released", "Built on 3nm process"],
          "future_opinions": ["Analysts expect a 15% revenue bump"],
          "entities": ["AAPL", "Apple", "TSMC"],
          "macro_themes": ["Technology", "Semiconductors"],
          "event_type": "Material Event",
          "hype_score": 45,
          "impact_score": 85,
          "source": "Yahoo Finance",
          "published_at": "2023-10-27T09:00:00Z"
        }
      ]
    }
    ```

**2. Time-Series Trend Data (Upcoming)**
*   **Endpoint:** `GET /api/trends/{ticker}`
*   **Purpose:** Formatted directly for Trust's Nivo charting library to overlay hype/impact scores onto price charts.
*   **Payload Returns:** Array of X/Y coordinates mapping dates to sentiment/impact scores.

### B. What Trust Passes to Intelligence (The Configuration)

**1. Update Portfolio Targets (Upcoming)**
*   **Endpoint:** `POST /api/config/targets`
*   **Purpose:** Trust tells Intelligence which tickers the user owns, so the ingestion daemon can prioritize those feeds.
*   **Payload Expects:**
    ```json
    {
      "watch_tickers": ["AAPL", "MSFT", "GBX"],
      "macro_themes": ["Interest Rates", "AI Regulation"]
    }
    ```

**2. Source Reliability Toggles (Upcoming)**
*   **Endpoint:** `POST /api/config/sources`
*   **Purpose:** If the user identifies a news source as "too noisy" via the UI, Trust tells Intelligence to mute it.
*   **Payload Expects:**
    ```json
    {
      "source_name": "Motley Fool",
      "status": "muted"
    }
    ```

## 4. Source Governance
*   **Control:** The `Intelligence` backend daemon (`ingestor.py`) strictly controls the polling frequency, scraping logic, and AI rate limits to protect API keys and database locks.
*   **Trust's Role:** Trust acts as the commander, passing down the "Target List", but Intelligence executes the mission parameters independently.
