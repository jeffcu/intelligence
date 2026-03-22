-- Telemetry Vault: Tracking AI Usage and System Performance

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    provider TEXT DEFAULT 'google_gemini',
    model_id TEXT,
    request_type TEXT, -- e.g., 'summarization', 'tagging', 'deduplication'
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd REAL,
    latency_ms INTEGER,
    status_code INTEGER
);

CREATE TABLE IF NOT EXISTS source_performance (
    source_name TEXT PRIMARY KEY,
    total_articles_ingested INTEGER DEFAULT 0,
    redundant_articles_chopped INTEGER DEFAULT 0,
    average_hype_score REAL DEFAULT 0.0,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);