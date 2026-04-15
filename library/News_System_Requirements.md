# System Requirements: Personal News Intelligence Module (Decoupled Microservice)

## 1. Purpose
This module is an independent, heavily-decoupled intelligence layer designed to gather, normalize, and distill global news into a peaceful, simple, and highly readable format. It serves as an experimental sandbox for tuning data extraction and gracefully integrating with the core 'Trust' engine.

## 2. Core Objective
To provide peace and clarity. Given a specific portfolio and macro topics injected by the Trust UI, the module will run a continuous, staggered background collection to maintain real-time awareness without expensive premium APIs. It will rigorously deduplicate overlapping coverage, extract dynamic tags, and generate an objective briefing.

**Token Efficiency is a first-class constraint.** The AI engine (Gemini) is only ever invoked on articles that have passed all local filters. Irrelevant, duplicate, or low-signal content is incinerated before any API call is made.

---

## 3. Dynamic Target Lock System

The engine must be dynamically aimable via the Trust UI and the Intelligence Tuning Console. Target Locks define what the system cares about.

### 3.1 Target Lock Categories
| Type | Examples | Purpose |
|---|---|---|
| `Ticker` | AAPL, NVDA, BRK.B | Public equity holdings from Trust portfolio |
| `Macro` | Gold, Bitcoin, Interest Rates, Oil | Broad macro themes affecting the portfolio |
| `Company` | SpaceX, OpenAI | Private companies of strategic interest |
| `Person` | Jerome Powell, Elon Musk | Key market-moving figures |
| `Subject` | Tariffs, Fed Policy, Earnings Season | Thematic subjects to monitor |

### 3.2 Target Lock Keyword Expansion
A raw ticker symbol ("AAPL") is insufficient for broad-source matching. The system must maintain a **keyword expansion map** that translates each Target Lock into a set of search terms used across all ingestion tiers.

- **Requirement:** Each `Ticker` target must resolve to: ticker symbol, full company name, CEO name, and primary product lines (e.g., `AAPL` → `["AAPL", "Apple", "Tim Cook", "iPhone", "Mac", "App Store"]`).
- **Requirement:** Keyword expansion data must be stored in the database (`target_keywords` table) and be editable via the API.
- **Requirement:** Expansion can be seeded automatically (via a one-time lookup to a free source like Yahoo Finance metadata) or entered manually. Manual override must always be possible.

### 3.3 Trust Portfolio Synchronization
- **Requirement:** The Intelligence API must expose `POST /api/targets/sync` that accepts a list of tickers and upserts them into `target_locks`.
- **Requirement:** Trust's NewsView must call this endpoint automatically on load, not only on button press, using the live portfolio from `/api/analysis/portfolio-chart`.
- **Requirement:** The sync must be additive — it never removes a target that was manually added via the Tuning Console.

---

## 4. The 4-Tier Ingestion Stack (The Sensor Array)

Sources are organized by reliability, latency, and relevance density. Each tier polls at a different frequency.

| Tier | Type | Sources | Poll Frequency |
|---|---|---|---|
| 1 | Broad News (RSS) | Google News RSS (dynamic), Reuters, AP News | Every 15 min |
| 2 | Markets & Data (API) | Marketaux (free), Alpha Vantage, FRED, Finnhub | Every 30 min |
| 3 | Primary Truth (Official) | SEC EDGAR RSS, WhiteHouse.gov, Fed Reserve press releases | Every 60 min |
| 4 | High-Signal Alerts (Email) | Google Alerts via IMAP, Investor Relations emails, Business Wire, GlobeNewswire | Continuous IMAP IDLE listener |

### 4.1 Dynamic Feed Construction
- **Requirement:** Tier 1 Google News RSS URLs must be dynamically constructed from active Target Locks at ingestion time. Format: `https://news.google.com/rss/search?q=AAPL+OR+Apple+OR+Tim+Cook&hl=en-US&gl=US&ceid=US:en`
- **Requirement:** The query must be rebuilt each poll cycle in case Target Locks have changed.
- **Requirement:** If the total number of active keywords exceeds Google News query limits, the system must split them into multiple parallel queries, one per target category.

### 4.2 Email Ingestion (Tier 4)
- **Requirement:** The system must connect to a configured Gmail/IMAP account using app-password credentials stored in `.env`.
- **Requirement:** An IMAP IDLE listener must run continuously and process new emails as they arrive.
- **Requirement:** Sender allowlist must be configurable (only process emails from trusted senders — e.g., `alerts@google.com`, `noreply@businesswire.com`).
- **Requirement:** Email subject and body are treated as the article text and passed through the standard 3-level processing pipeline.
- **Requirement:** Processed emails must be marked as read and optionally moved to a configured archive label/folder to prevent reprocessing.

---

## 5. The 3-Level Processing Pipeline

Every article from every source passes through all three levels in order. Levels 1 and 2 are zero-cost local operations. Level 3 is the only step that costs money.

### Level 1 — The Deflector (Keyword Relevance Filter)
**This is the primary token-saving mechanism.**

- **Requirement:** Before any other processing, the system must check whether the article title or body contains at least one keyword from the active `target_keywords` set (case-insensitive).
- **Requirement:** Articles with zero keyword matches must be silently discarded. No database write. No vector operation. No AI call.
- **Requirement:** The discard must be logged as a count in `source_performance` (`deflected_articles`) for tuning visibility.
- **Requirement:** The keyword match must use whole-word matching where practical to avoid false positives (e.g., "gold" should not match "golden").
- **Requirement:** Match threshold is configurable — default is 1 keyword match required. A future tuning option may require 2+ matches for noisy sources.

### Level 2 — Semantic Deduplication (ChromaDB Chopper)
- **Requirement:** Articles that pass Level 1 are embedded locally and compared against the existing ChromaDB collection.
- **Requirement:** Articles with cosine similarity > 0.85 to an existing vector are "chopped" — discarded without an AI call.
- **Requirement:** Chop events are logged in `source_performance` (`redundant_articles_chopped`).

### Level 3 — De-Hype Engine (Gemini AI Extraction)
Only articles that pass Levels 1 and 2 reach this stage.

- **Requirement:** The Gemini prompt must include the active Target Locks as context: *"The user holds the following positions and monitors these subjects: [list]. Score relevance to these specifically."*
- **Requirement:** The extracted `entities` list must be cross-referenced against `target_locks` to populate a `matched_targets` field (JSON array) on the article record. This powers relevance filtering in the Trust UI.
- **Requirement:** `hype_score`, `impact_score`, and `matched_targets` are all required fields. Articles with extraction failures must be flagged with `event_type = "Error"` and excluded from Trust UI responses.
- **Requirement:** All AI calls must be logged in `ai_usage_logs` with token counts, latency, and estimated cost.

---

## 6. Data Schema Requirements

### `target_locks` (exists)
`id, target_type, target_value, added_at`

### `target_keywords` (new)
`id, target_lock_id (FK), keyword, added_at`
- One-to-many from `target_locks`. Stores the expanded keyword set for each target.

### `articles` (extend)
Add: `matched_targets TEXT` (JSON array of target_lock IDs or values that matched this article)

### `source_registry` (extend)
Add: `deflected_articles INTEGER DEFAULT 0` to `source_performance`

---

## 7. API Contract Requirements

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/targets` | GET | List all active target locks |
| `/api/targets` | POST | Add a single target lock |
| `/api/targets/{id}` | DELETE | Remove a target lock |
| `/api/targets/sync` | POST | Bulk upsert from Trust portfolio (accepts `{ tickers: [...] }`) |
| `/api/targets/{id}/keywords` | GET | List expansion keywords for a target |
| `/api/targets/{id}/keywords` | POST | Add a keyword to a target's expansion set |
| `/api/briefing/latest` | GET | All processed articles, sorted by signal score |
| `/api/briefing/latest?target=AAPL` | GET | Filter briefing by a specific matched target |
| `/api/telemetry/stats` | GET | Aggregate AI cost, latency, deflect/chop rates |
| `/api/sources` | GET | List all sources with per-source performance |

---

## 8. Architectural Design Principles (The Scotty Doctrine)

- **Total Decoupling:** The Intelligence Engine runs as a standalone backend process. Trust never calls the ingestor directly.
- **Zero-Waste Query Policy:** Never send junk to the AI. Filter locally first. The Deflector is the shield. The Chopper is the backup.
- **Dumb Client, Smart Server:** The Trust UI fetches pre-compiled pristine JSON. It does not do filtering or scoring.
- **Zero-Cost Infrastructure:** 100% open-source, embedded architecture (SQLite, ChromaDB local embeddings).
- **Async Always:** The ingestion daemon is non-blocking. The API and the daemon are independent processes.
- **Targets Drive Everything:** Every ingestion decision — what to fetch, what to filter, what to send to AI — is derived from the active `target_locks`. The system has no hardcoded interests.
