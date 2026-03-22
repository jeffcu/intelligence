# System Requirements: Personal News Intelligence Module (Decoupled Microservice)

## 1. Purpose
This module is an independent, heavily-decoupled intelligence layer designed to gather, normalize, and distill global news into a peaceful, simple, and highly readable format. It serves as an experimental sandbox for tuning data extraction (tags/counters) and gracefully integrating with the core 'Trust' engine.

## 2. Core Objective
To provide peace and clarity. Given a portfolio of tickers and global feeds, the module will ingest source material, rigorously deduplicate overlapping coverage (redundant chopping), extract dynamic tags and counters, and generate a concise, objective daily briefing free of sensationalism.

## 3. Functional Scope
*   **Inputs:** Portfolio watchlist of tickers, scalable global news feeds (RSS/APIs/Newsletters).
*   **Processing:** Semantic deduplication (Chopping), dynamic tagging, entity counting, and 'De-Hype' objective normalization.
*   **Outputs:** Structured JSON summary object exposed via a dedicated REST API endpoint.
*   **Telemetry:** Time-series plotting of tag frequencies and source noise-levels.

## 4. Architectural Design Principles (The Scotty Doctrine)
*   **Total Decoupling:** The Intelligence Engine runs as a standalone backend process.
*   **Asynchronous Processing:** Heavy tasks operate entirely in the background to ensure peace and stability on the main thread.
*   **Dumb Client, Smart Server:** The Trust UI (React) simply fetches the pre-compiled, pristine JSON and renders it beautifully.
*   **Traceability & Tuning:** The Tuning Console acts as an experimental sandbox to dial in LLM prompts, test new tags, and monitor source quality.
*   **Zero-Cost Infrastructure:** 100% open-source, embedded architecture (SQLite/DuckDB, ChromaDB).

## 5. High-Level Architecture
1.  **Scalable Ingestion Daemon:** Plug-and-play Python workers pulling varying data sources.
2.  **Processing Pipeline:** Deduplication (Chopping) -> Tag/Counter Extraction -> LLM Summarization.
3.  **Local Datastore:** 
    *   Relational Data: SQLite (Articles, Telemetry).
    *   Vector Data: ChromaDB (Embeddings for semantic deduplication).
4.  **Briefing API:** FastAPI layer exposing `/api/briefing/latest` and `/api/trends/{tag}`.
5.  **Tuning Console:** React sandbox to experiment with prompt tuning and view redundant chopping efficiency.