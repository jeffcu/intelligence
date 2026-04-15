# Intelligence Module: API Contract

## 1. System Overview
*   **Base URL:** `http://localhost:8001`
*   **Service Name:** Intelligence Telemetry API
*   **Purpose:** Serves mathematically de-hyped, AI-processed global news and intelligence telemetry to the core Trust dashboard.
*   **CORS Policy:** Whitelisted for `http://localhost:5173` and `http://127.0.0.1:5173` (Trust React Dev Servers).

---

## 2. Core Endpoints (The Briefing Feed)

### GET `/api/briefing/latest`
Fetches the most recent, normalized intelligence briefings. 
*   **Query Parameters:** `limit` (int, default=50)
*   **Response (200 OK):**
```json
{
  "briefings": [
    {
      "id": 105,
      "title": "Apple Announces M4 Chip",
      "summary": "Raw scraped summary text...",
      "dehyped_summary": "Apple has released the M4 processor with a focus on neural engine performance.",
      "current_facts": ["M4 chip released", "Built on 3nm process"],
      "future_opinions": ["Analysts expect a 15% revenue bump"],
      "entities": ["AAPL", "Apple", "TSMC"],
      "macro_themes": ["Technology", "Semiconductors"],
      "event_type": "Material Event",
      "hype_score": 45,
      "impact_score": 85,
      "source": "Yahoo Finance",
      "link": "https://finance.yahoo.com/...",
      "published_at": "2023-10-27T09:00:00Z"
    }
  ]
}
```

### GET `/api/graph`
Fetches gravimetric node and link data for rendering the Knowledge Graph.
*   **Response (200 OK):**
```json
{
  "nodes": [
    { "id": "AAPL", "group": "entity", "val": 5.2 }
  ],
  "links": [
    { "source": "Yahoo Finance", "target": "AAPL", "impact": 85, "title": "Article Title", "date": "2023-10-27..." }
  ]
}
```

---

## 3. Dynamic Target Locks (Aiming the Array)

### GET `/api/targets`
Lists all active intelligence target locks.
*   **Response (200 OK):** Array of target objects `[{"id": 1, "target_type": "Macro", "target_value": "Gold", "added_at": "..."}]`

### POST `/api/targets`
Acquires a new sensor lock on a specific entity, ticker, or macro theme.
*   **Payload:**
```json
{
  "target_type": "Company|Ticker|Macro|Person",
  "target_value": "NVIDIA"
}
```
*   **Response (200 OK):** `{"status": "success", "message": "Target lock acquired..."}`

### DELETE `/api/targets/{target_id}`
Releases an existing target lock.
*   **Response (200 OK):** `{"status": "success", "message": "Target lock released."}`

---

## 4. Source Governance (Managing the Feeds)

### GET `/api/sources`
Retrieves the telemetry and status of all registered source frequencies.
*   **Response (200 OK):** Array of source objects including telemetry: `[{"source_name": "Reuters", "feed_url": "...", "is_active": 1, "total_articles_ingested": 142, "redundant_articles_chopped": 89, "average_hype_score": 42.5}]`

### POST `/api/sources`
Adds a new RSS/API feed to the ingestion matrix.
*   **Payload:**
```json
{
  "source_name": "Financial Times",
  "feed_url": "https://www.ft.com/..."
}
```
*   **Response (200 OK):** `{"status": "success", "message": "Source added..."}`

### PUT `/api/sources/{source_name}/toggle`
Engages or disengages the deflector shields for a specific source (Toggles `is_active` 1/0).
*   **Response (200 OK):** `{"status": "success", "message": "Source toggle flipped."}`

---

## 5. Engineering Telemetry & Diagnostics

### GET `/health`
Verifies the SQLite Matrix and basic application state.
*   **Response (200 OK):** `{"status": "online", "matrix_path": "intelligence.db", "articles_table_ready": true}`

### GET `/api/telemetry/stats`
Retrieves operational metrics, including AI costs and deduplication performance.
*   **Response (200 OK):**
```json
{
  "total_stored": 1250,
  "total_chopped": 430,
  "ai_calls": 1250,
  "total_tokens": 850000,
  "total_cost_usd": 0.125045,
  "avg_latency_ms": 1450.2
}
```
