# Scotty's Research & Development Log

## Active Project: Awesome-Finance-Skills Extraction
**Status:** Extraction Complete. Ready for Implementation.
**Source Origin:** `projects/intelligence/awesome_finance/` (Jettisoned to Cold Storage)

### Objective Checklist
- [x] **Prompt Evolution:** Extracted the ISQ (Investment Signal Quality) mathematical framework from `alphaear-signal-tracker`. We will map this to `dehype.py`.
- [x] **Taxonomy Expansion:** Extracted macro-theme and event-type schemas. Expanded Pydantic models in `ingestor.py`.
- [x] **Source Mining:** Extracted Polymarket API (`gamma-api.polymarket.com`) for predictive market probabilities.
- [x] **Ingestion Upgrade (MODIFIED):** Discovered the concept of HTML-to-Markdown extraction for pristine LLM context. *Captain vetoed 3rd-party API reliance.* We will build this locally.

### Engineering Notes & Extracted Blueprints

#### 1. The ISQ Mathematical Matrix (For De-Hype Engine)
To mathematically lock our `impact_score` and `hype_score`, we will adopt the AlphaEar ISQ dimensions:
*   **Sentiment:** -1.0 (Extreme Bear) to 1.0 (Extreme Bull)
*   **Confidence (确定性):** 0.0 to 1.0 (Information reliability)
*   **Intensity (强度):** 1 to 5 (Magnitude of impact. 1 = weak, 5 = market-shifting)
*   **Expectation Gap (预期差):** 0.0 to 1.0 (0.0 = Priced in, 1.0 = Massive shock/Alpha)
*   **Timeliness (时效性):** 0.0 to 1.0 (Reaction window)

**Calculated Impact Score Formula:**
We will instruct the Gemini 2.5 Flash prompt to evaluate these 5 dimensions, then output an `impact_score` out of 100 based on the formula:
`Impact = ((Confidence * 0.35) + ((Intensity/5) * 0.30) + (Expectation_Gap * 0.20) + (Timeliness * 0.15)) * 100`

**Calculated Hype Score Formula:**
`Hype_Score` will be determined by the delta between the emotional sentiment of the raw text and the factual `Confidence` score.

#### 2. Localized HTML-to-Markdown Extraction (The "Jina Clone")
Instead of relying on `r.jina.ai`, we will upgrade `fetch_article_text` in `projects/intelligence/ingestor.py` to locally convert HTML into Markdown. This retains structural purity for Gemini while keeping our telemetry 100% private and zero-cost.

#### 3. ARC2 Architecture Note
The `skill-creator` module demonstrates a highly efficient, context-saving agent architecture using progressive disclosure (`SKILL.md` + `references/`). We will adopt this standard for our future agent ecosystem to save on context window token costs.