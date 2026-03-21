# Intelligence Module: Build Plan (The Thin Thread)

## Phase 1: The Tracer Bullet (Ingest & Serve)
*   **Goal:** Establish the end-to-end pipeline without AI overhead to ensure system connectivity.
*   **Steps:**
    1. Scaffold `projects/intelligence/` directory structure.
    2. Define static mock schemas in `projects/intelligence/tests/mock_data/`.
    3. Spin up local DuckDB instance (or SQLite if DuckDB is overkill for Phase 1).
    4. Build lightweight Python Ingestor daemon to pull a single RSS feed (e.g., Yahoo Finance).
    5. Build FastAPI `/api/briefing/latest` endpoint connected to the DB.
    6. Scaffold the Tuning Console (`projects/intelligence/tuning-console`) in React to display raw DB rows.

## Phase 2: The De-Hype Engine (LLM Integration)
*   **Goal:** Strip sensationalism, normalize data, output dry, objective intelligence.
*   **Steps:**
    1. Wire the chosen LLM API into the ingestion pipeline asynchronously.
    2. Implement the "Objective Normalization" system prompt.
    3. Calculate the Sensationalism Delta ($\Delta$).
    4. Update DB schema to store `hype_score`, `impact_score`, and `dehyped_summary`.
    5. Update Tuning Console to side-by-side compare Raw vs. De-Hyped text.

## Phase 3: Telemetry & The Source Credibility Index (SCI)
*   **Goal:** Expose trends over time and mathematically rank news sources by reliability.
*   **Steps:**
    1. Write aggregation logic in DuckDB for SCI based on historical Sensationalism Deltas.
    2. Create `/api/trends/{ticker}` FastAPI endpoint to output time-series JSON.
    3. Add Source Credibility ranking tables to the Tuning Console.

## Phase 4: Main Engine Integration (Trust UI)
*   **Goal:** Wire the weaponized, de-hyped data into the main financial dashboard.
*   **Steps:**
    1. Update `projects/trust/src/components/NewsView.jsx` to fetch from the Intelligence API.
    2. Map the existing Nivo charting library to the `/api/trends` endpoints to plot noise vs. signal directly over price charts.
    3. Final load testing and system integration checks.