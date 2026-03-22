# Intelligence Module: Build Plan (The Thin Thread)

## Phase 1: The Tracer Bullet (Ingest & Serve) [COMPLETED]
*   **Goal:** Establish the end-to-end pipeline without AI overhead to ensure system connectivity.
*   **Steps:**
    1. Scaffold `projects/intelligence/` directory structure. [DONE]
    2. Define static mock schemas in `projects/intelligence/tests/mock_data/`. [DONE]
    3. Spin up local DuckDB/SQLite instance. [DONE]
    4. Build lightweight Python Ingestor daemon. [DONE]
    5. Build FastAPI `/api/briefing/latest` endpoint. [DONE]

## Phase 2: The Tuning Sandbox & Telemetry (The Lab)
*   **Goal:** Build an experimental workbench to tune data and track AI costs/performance.
*   **Steps:**
    1. **Scaffold the Tuning Console:** Build `projects/intelligence/tuning-console` in React to act as an experimental UI.
    2. **API Telemetry Vault:** Implement a `telemetry` table in the local DB to log every Gemini call, token count, and cost estimate.
    3. **Implement Redundant Chopping:** Group overlapping news stories by semantic similarity. Merge multiple articles into single, clear summaries to save on LLM processing.
    4. **Tagging & Counters:** Tune the LLM prompt to dynamically generate category tags, entity counters, and theme classifications.

## Phase 3: Source Serenity & Analytics
*   **Goal:** Expose trends over time and identify which sources provide the highest signal-to-noise ratio.
*   **Steps:**
    1. Write aggregation logic in the DB based on tagging frequency and noise scores.
    2. Create `/api/trends/{ticker}` FastAPI endpoint to output time-series JSON.
    3. Add Source Reliability views to the Tuning Console to easily toggle off noisy feeds.

## Phase 4: Main Engine Integration (Trust UI)
*   **Goal:** Seamlessly flow the simple, clean data into the main financial dashboard.
*   **Steps:**
    1. Update `projects/trust/src/components/NewsView.jsx` to fetch from the Intelligence API.
    2. Map the existing Nivo charting library to plot simple trend tags over price charts.
    3. Final load testing and system integration checks.