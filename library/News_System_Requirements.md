# System Requirements: Personal News Intelligence Module (Decoupled Microservice)

## 1. Purpose
This module is an independent, heavily-decoupled intelligence layer designed to gather, normalize, analyze, condense, and present relevant news for the user. It is separated from the core 'Trust' financial engine to prevent code bloat, ensure high performance of the desktop app, and allow asynchronous, heavy LLM processing without freezing the primary user interface.

## 2. Core Objective
Given a portfolio of tickers (pulled via API from Trust) and global-interest topics, the module will ingest source material on a scheduled basis, convert it into a common internal format, deduplicate overlapping coverage, strip sensationalism, and generate a concise, highly objective daily briefing.

## 3. Functional Scope
*   **Inputs:** Portfolio watchlist of tickers, curated global news feeds (RSS/APIs), email newsletter sources, and user preferences.
*   **Processing:** Deduplication, semantic matching, sentiment analysis, and 'De-Hype' objective normalization.
*   **Outputs:** Structured JSON summary object exposed via a dedicated REST API endpoint.
*   **Telemetry:** Time-series plotting of asset news trends and a running 'Source Credibility Index' (SCI).

## 4. Architectural Design Principles (The Scotty Doctrine)
*   **Total Decoupling:** The Intelligence Engine runs as a standalone backend process (e.g., on port 8001 or a remote cloud server).
*   **Asynchronous Processing:** Heavy tasks (LLM summarization, web scraping) operate entirely in the background.
*   **Dumb Client, Smart Server:** The Trust UI (React) does zero processing. It simply fetches the pre-compiled briefing JSON and renders it.
*   **Traceability & Accountability:** Raw source material remains available to explain *why* an item was included and to score the source's sensationalism.
*   **Zero-Cost Infrastructure:** Absolutely no commercial database licenses or enterprise fees. 100% open-source, embedded architecture.

## 5. High-Level Architecture
1.  **Independent Ingestion Daemon:** Python-based scheduled workers pulling RSS/API data.
2.  **Processing Pipeline:** Normalization -> Ticker Matching -> Deduplication -> Sensationalism Scoring -> LLM 'De-Hype' Summarization.
3.  **Local Datastore (Analytical):** Embedded DuckDB (MIT License). Runs in-process with zero network overhead. Optimized specifically for fast OLAP column aggregations required by the SCI and trend telemetry.
4.  **Briefing API:** A lightweight FastAPI layer exposing:
    *   `GET /api/briefing/latest` (The daily digest)
    *   `GET /api/trends/{ticker}` (Time-series sentiment/volume data)
    *   `GET /api/sources/reliability` (The Source Credibility Index rankings)
5.  **Trust UI / Tuning Console Integration:** React components to consume APIs, plot trendlines, and visualize source reliability warnings.

## 6. Phased Rollout Plan
*   **Phase 1 (Decoupled MVP):** Scaffold independent project (`projects/intelligence`). Basic RSS ingestion, embedded DuckDB setup, deterministic ticker matching, and the FastAPI base. 
*   **Phase 2 (The Tuning Console & De-Hype Layer):** Build `projects/intelligence/tuning-console` to visually tune LLM prompts. Introduce AI summarization to aggressively strip emotional language and calculate the Sensationalism Delta.
*   **Phase 3 (Portfolio Sync & Telemetry):** Intelligence Engine dynamically polls Trust API. Trust UI integrates Nivo charts to plot `/api/trends` and SCI warnings.
*   **Phase 4 (Advanced Ingestion):** Gmail/IMAP integration for newsletters, SEC filings.

## 7. Recommended Stack
*   **Backend:** Python 3.11+, FastAPI (Port 8001), APScheduler/Celery for background jobs.
*   **Storage:** DuckDB (Primary - MIT License) or LanceDB (Fallback for vector embeddings - Apache 2.0). Both are free, embedded, and require no standalone server.
*   **Frontend (Tuning Console & Trust):** React 18, utilizing existing Nivo charts for trend plotting.