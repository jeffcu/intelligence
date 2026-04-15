# Intelligence Module: Test Protocol

## Phase 1 & 2: Pipeline & De-Hype Engine [COMPLETED]
- [x] Ingestion pulls RSS items and writes to SQLite without crashing
- [x] `GET /api/briefing/latest` returns HTTP 200 and valid JSON
- [x] Tuning Console renders database rows visually
- [x] `hype_score` and `impact_score` populated with 0–100 integers
- [x] Emotional adjectives eradicated from `dehyped_summary`

## Phase 3: Dynamic Targeting & Source Governance [COMPLETED]
- [x] `GET /api/targets` returns active target lock list
- [x] `POST /api/targets` adds a target and persists it across restarts
- [x] Trust "Target Lock" button pushes top 10 tickers to `/api/targets`
- [x] Ingestor reads active sources from `source_registry` at startup

---

## Phase 4: Portfolio-Aware Token-Efficient Pipeline [CURRENT]

### 4.1 — Level 1 Deflector
- [ ] **True Negative:** Inject a clearly irrelevant article (e.g., cat food recall) into the pipeline manually. Confirm: zero DB write, zero ChromaDB op, zero AI call, deflect count incremented in `source_performance`.
- [ ] **True Positive:** Inject an article mentioning "Apple quarterly earnings." Confirm: passes Deflector (AAPL target active), proceeds to Level 2.
- [ ] **Case Insensitivity:** Article containing "APPLE" (uppercase) matches target keyword "apple". Confirm pass.
- [ ] **Whole-Word Guard:** Article containing "golden retriever" does not match target keyword "gold". Confirm deflect.
- [ ] **Zero Targets Edge Case:** With no active target locks, confirm all articles are deflected (or system logs a warning and halts ingestion gracefully).

### 4.2 — Dynamic Feed Construction
- [ ] **URL Construction:** With targets `AAPL`, `Bitcoin`, `Jerome Powell` active, confirm the constructed Google News RSS URL contains all three (or their expanded keywords) and is a valid fetchable URL.
- [ ] **Rebuild on Change:** Add a new target lock via the API. Restart the daemon. Confirm the new target appears in the next constructed RSS query.
- [ ] **Query Split:** Add enough targets to exceed a single URL's practical length. Confirm the system constructs multiple queries rather than a single malformed URL.

### 4.3 — Target-Aware Prompt Injection
- [ ] **Prompt Content:** Log a raw Gemini prompt during a test run. Confirm the active target locks appear in the prompt context section.
- [ ] **matched_targets Populated:** Process an article that mentions "Apple" when AAPL is an active target. Confirm `matched_targets` on the saved article record includes AAPL.
- [ ] **No Match:** Process an article about a macro theme (e.g., oil prices) when only Ticker targets are active. Confirm `matched_targets` is an empty array (not null).

### 4.4 — Trust Portfolio Auto-Sync
- [ ] **Auto-sync on Load:** Open Trust NewsView with a portfolio containing NVDA. Confirm `target_locks` in Intelligence DB contains NVDA without the user pressing any button.
- [ ] **Additive Only:** Manually add `Gold` as a Macro target via the Tuning Console. Load Trust. Confirm `Gold` is not removed after the auto-sync runs.
- [ ] **`POST /api/targets/sync` Contract:** POST `{ "tickers": ["MSFT", "GOOG"] }` directly. Confirm both are upserted. POST again — confirm no duplicates created.

### 4.5 — Async Continuous Daemon
- [ ] **Non-Blocking:** Start the async daemon. Confirm the FastAPI server on port 8001 remains responsive (returns 200 on `/health`) while an ingestion cycle is actively running.
- [ ] **Staggered Polling:** Monitor logs over 60 minutes. Confirm Tier 1 sources poll ~4x, Tier 2 ~2x, Tier 3 ~1x.
- [ ] **Graceful Shutdown:** Send SIGINT to the daemon process. Confirm it finishes its current in-progress article (no partial DB write) and exits cleanly.

### 4.6 — Email Ingestion
- [ ] **IMAP Connection:** With valid `.env` credentials, confirm daemon connects to IMAP and begins IDLE without error.
- [ ] **Allowlist Enforcement:** Send a test email from a non-allowlisted address. Confirm it is ignored entirely.
- [ ] **End-to-End:** Send a Google Alert email about an active target (e.g., "Apple signs deal with..."). Confirm: email processed, article written to DB with correct `source = 'Google Alerts'`, email marked read in Gmail.
- [ ] **Deflector Applied:** Send a Google Alert email about an irrelevant topic. Confirm it is deflected at Level 1, no DB write, email still marked read.
- [ ] **No Reprocessing:** Trigger the IMAP listener twice on the same inbox state. Confirm already-processed (read) emails are not processed again.

---

## Phase 5: Trust UI Stratification [NEXT]

- [ ] `GET /api/briefing/latest?target=AAPL` returns only articles where `matched_targets` includes AAPL.
- [ ] Trust NewsView groups articles by matched target with clear visual lane separation.
- [ ] Macro articles (matched to Macro/Subject targets) rendered in a separate section from equity articles.
- [ ] Telemetry panel displays deflect rate, chop rate, and weekly AI cost. Values match `source_performance` and `ai_usage_logs` DB state.

---

## Phase 6: Signal Quality [FUTURE]

- [ ] Source with consistently high `hype_score` articles is mathematically demoted by SCI over a 7-day window.
- [ ] `/api/trends/AAPL` returns time-series array of impact/hype scores formatted for Nivo.
- [ ] Tuning Console displays per-source SCI, deflect count, chop count, and enable/disable toggle.
