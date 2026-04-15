# Intelligence Module: Build Plan

## Phase 1 & 2: Tracer Bullet & Vector NoSQL [COMPLETED]
- End-to-end pipeline established (ingest → SQLite → FastAPI → React)
- ChromaDB semantic deduplication integrated
- Gemini 2.5 Flash de-hype engine operational
- `ai_usage_logs` and `source_performance` telemetry tables live

## Phase 3: Dynamic Targeting & Source Governance [COMPLETED]
- `target_locks` table and `GET/POST/DELETE /api/targets` endpoints built
- `source_registry` table added; ingestor reads active sources dynamically
- Trust NewsView wired to Intelligence API at port 8001
- Trust "Target Lock: Top Assets" button pushes top 10 portfolio tickers to `/api/targets`

---

## Phase 4: Portfolio-Aware Token-Efficient Pipeline [CURRENT]

**Goal:** Make the system actually use target locks to guide ingestion. Every article that enters the pipeline must be evaluated for portfolio relevance *before* any AI token is spent. Targets must drive feed construction, filtering, and prompt context.

### 4.1 — Level 1 Deflector (Keyword Relevance Filter)
- [ ] Add `target_keywords` table: `(id, target_lock_id FK, keyword, added_at)`
- [ ] Seed keyword expansion on target creation: ticker → company name, CEO, primary products (manual seed initially; auto-lookup later)
- [ ] Implement `deflect_article(title, summary, keywords) → bool` function in `ingestor.py`
- [ ] Gate the entire processing pipeline behind this check — zero DB writes, zero vector ops, zero AI calls on deflected articles
- [ ] Log deflected count to `source_performance.deflected_articles` (add column)
- [ ] Add `GET /api/targets/{id}/keywords` and `POST /api/targets/{id}/keywords` endpoints

### 4.2 — Dynamic Feed Construction
- [ ] Replace hardcoded RSS URLs in `ingestor.py` with dynamic Google News RSS builder
- [ ] Builder reads active `target_locks` + their `target_keywords` at daemon startup
- [ ] Construct one RSS query per target category (Ticker, Macro, Person, Subject) to stay within URL length limits
- [ ] Format: `https://news.google.com/rss/search?q=AAPL+OR+Apple+OR+%22Tim+Cook%22&hl=en-US&gl=US&ceid=US:en`
- [ ] Add SEC EDGAR RSS as a fixed Tier 3 source (no dynamic construction needed)

### 4.3 — Target-Aware Prompt Injection
- [ ] At ingest time, load active `target_locks` into memory
- [ ] Inject as context into every Gemini prompt: *"The user monitors these positions and subjects: [list]. Factor relevance to these when scoring impact."*
- [ ] After AI extraction, cross-reference returned `entities` against `target_locks` to compute `matched_targets` (JSON array)
- [ ] Store `matched_targets` on the `articles` record (add column)

### 4.4 — Trust Portfolio Auto-Sync
- [ ] Add `POST /api/targets/sync` endpoint: accepts `{ tickers: ["AAPL", "NVDA", ...] }`, upserts into `target_locks` without touching manually-added targets
- [ ] Update `NewsView.jsx` in Trust: call `/api/targets/sync` automatically on component mount using the live portfolio data, not only on button press

### 4.5 — Async Continuous Daemon
- [ ] Refactor `ingestor.py` to use `asyncio` with independent per-source polling loops
- [ ] Tier 1 (RSS): poll every 15 minutes
- [ ] Tier 2 (Market APIs): poll every 30 minutes
- [ ] Tier 3 (Official): poll every 60 minutes
- [ ] Daemon runs indefinitely; process is started once and left running
- [ ] Graceful shutdown on SIGINT/SIGTERM

### 4.6 — Email Ingestion (Tier 4)
- [ ] Add IMAP IDLE listener using `imaplib` or `aioimaplib` for async
- [ ] Configure via `.env`: `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWORD`, `IMAP_FOLDER`, `IMAP_ARCHIVE_LABEL`
- [ ] Sender allowlist stored in `source_registry` with `source_type = 'email'`
- [ ] Incoming emails pass through the same 3-level pipeline (Deflector → Chopper → AI)
- [ ] Processed emails marked as read and moved to archive label

---

## Phase 5: Trust UI Stratification & Briefing Views [NEXT]

**Goal:** Surface intelligence in Trust in a structured, portfolio-aligned way.

- [ ] `GET /api/briefing/latest?target=AAPL` — filter by matched target
- [ ] Modify `NewsView.jsx` to render articles grouped by matched target (per-holding news lanes)
- [ ] Add macro lane (articles matched to Macro/Subject targets) separate from equity lane
- [ ] Telemetry panel in Trust showing deflect rate, chop rate, AI cost this week

---

## Phase 6: Signal Quality & Source Tuning [FUTURE]

**Goal:** Mathematically rank sources by signal quality over time and auto-suppress noise.

- [ ] Source Credibility Index (SCI): compute per-source average `impact_score - hype_score` over rolling 7-day window
- [ ] Auto-disable sources with SCI below configurable threshold
- [ ] `/api/trends/{ticker}` time-series endpoint for Nivo chart overlay in Trust
- [ ] Source management UI in Tuning Console: enable/disable, view SCI, inspect deflect/chop rates per source
