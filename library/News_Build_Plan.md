# Intelligence Module: Build Plan (The Thin Thread)

## Phase 1: The Tracer Bullet (Ingest & Serve) [COMPLETED]
*   **Goal:** Establish the end-to-end pipeline without AI overhead to ensure system connectivity.
*   **Steps:**
    1. Scaffold `projects/intelligence/` directory structure. [DONE]
    2. Define static mock schemas in `projects/intelligence/tests/mock_data/`. [DONE]
    3. Spin up local SQLite instance for relational tracer bullet. [DONE]
    4. Build lightweight Python Ingestor daemon. [DONE]
    5. Build FastAPI `/api/briefing/latest` endpoint and Tuning Console UI. [DONE]

## Phase 2: Advanced Semantic Analytics & Vector NoSQL (The Lab) [IN PROGRESS]
*   **Goal:** Transition core intelligence collection to a NoSQL vector database (ChromaDB) to perform advanced semantic clustering, rapid visualizations, and eliminate duplicate token spend.
*   **Steps:**
    1. **Vector Containment Field:** Integrate ChromaDB into `projects/intelligence/ingestor.py` using a local embedding model (e.g., `all-MiniLM-L6-v2`) to prevent API costs during deduplication.
    2. **Redundant Chopping:** Implement semantic proximity checks. If a newly ingested article matches an existing vector clustering by >85%, silently drop or merge it before calling the LLM.
    3. **Prompt Evolution (Temporal Sorting):** Update the Gemini 2.5 Flash prompt to separate "Facts of the Now" from "Opinions of the Future".
    4. **Source Scaling:** Add the designated 10 RSS/JSON sources and lay scaffolding for email newsletter ingestion.
    5. **API Telemetry Vault:** Migrate tagging, counters, and token-cost tracking to dynamically log into the SQLite metadata store.

## Phase 3: Source Serenity & Analytics
*   **Goal:** Expose trends over time and identify which sources provide the highest signal-to-noise ratio.
*   **Steps:**
    1. Write aggregation logic based on tagging frequency and noise scores.
    2. Create `/api/trends/{ticker}` FastAPI endpoint to output time-series JSON.
    3. Add Source Reliability views to the Tuning Console to easily toggle off noisy feeds.

## Phase 4: Main Engine Integration (Trust UI)
*   **Goal:** Seamlessly flow the simple, clean data into the main financial dashboard.
*   **Steps:**
    1. Update `projects/trust/src/components/NewsView.jsx` to fetch from the Intelligence API.
    2. Map the existing Nivo charting library to plot simple trend tags over price charts.
    3. Final load testing and system integration checks.