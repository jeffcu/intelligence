# Intelligence Module: Test Protocol

## Phase 1: Tracer Bullet Validation
*   [ ] **Mock Data Contract:** `projects/intelligence/tests/mock_data/briefing_schema.json` correctly parses in frontend mock environment.
*   [ ] **Ingestion Flow:** Python daemon successfully pulls and writes 10 RSS items to local DB without crashing.
*   [ ] **API Health:** `curl localhost:8001/api/briefing/latest` returns HTTP 200 and structurally valid JSON.
*   [ ] **Tuning Console:** React dev server renders raw database rows visually. 

## Phase 2: De-Hype Engine Verification
*   [ ] **Prompt Efficacy:** Tuning console visually confirms emotional adjectives (e.g., "plummets", "skyrockets", "bloodbath") are eradicated in the output.
*   [ ] **Delta Math:** `hype_score` is successfully populated with a numerical value (e.g., 0 to 100).
*   [ ] **Async Performance:** LLM ingestion processes in the background. Tuning Console UI thread remains unblocked and responsive.

## Phase 3: Telemetry & SCI Auditing
*   [ ] **Trend API Output:** `/api/trends/AAPL` returns a chronological array of sentiment scores formatted for Nivo chart ingestion.
*   [ ] **SCI Logic Check:** Inject a mock news source into the DB with consistently high `hype_scores`. Verify the SCI mathematically demotes the source over a 5-day simulated period.

## Phase 4: UI Integration (Trust Dashboard)
*   [ ] **Non-Blocking Render:** Trust UI renders the news feed in under 200ms upon load.
*   [ ] **Visual Accuracy:** Nivo charts accurately plot hype (noise) vs factual sentiment (signal) overlays on top of existing portfolio telemetry.