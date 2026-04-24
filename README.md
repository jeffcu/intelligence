# Intelligence — Private Financial News Engine

A self-hosted service for private consumers who want to stay informed about assets they own or watch. Intelligence reads dozens of public news sources, strips opinion and hype, and surfaces only what actually happened — classified by event type, scored for significance, and summarized in plain language. No ads, no engagement algorithms, no subscription fees, no clickbait.

**This project is for personal, private use.** It is designed to help individuals identify factual developments that may affect the value of or risk associated with assets they follow — equities, commodities, currencies, macro conditions, or sectors. It does not provide investment advice.

---

## Purpose

Financial news is written to be read, not used. Every article that reaches a retail investor has already been filtered through an editorial lens optimized for engagement — dramatic headlines, speculative commentary, and narratives designed to provoke a reaction. The actual facts, when present at all, are buried in paragraph four and mixed with analyst opinions presented as established truth.

Intelligence inverts this. It reads the same public news sources you would read yourself, then does one job: separate what actually happened from what someone thinks might happen, score how significant the event is, and present only the factual content in a format you can absorb in thirty seconds.

The result is a private briefing service tuned to your specific holdings and topics of interest. If you follow five tickers and three macro themes, you get exactly that — not a general news stream you have to filter yourself.

---

## Quick Start

**Prerequisites:**
- [ ] [Docker Desktop](https://www.docker.com/products/docker-desktop) installed **and open** (look for the whale icon in your menu bar)
- [ ] A free Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (takes 30 seconds, no credit card)

**Run the setup script**

Clone or download this folder, open a terminal in it, and run:

```bash
bash setup.sh
```

The script checks Docker, creates your `.env` file, prompts for your API key, builds the container, and tells you exactly what to do next. The first build takes 2–4 minutes; after that, starts take 5 seconds.

**That's it for setup.** After the script finishes:

1. Open **http://localhost:8001** in your browser
2. Click **✎ Edit** in the Tracking panel — add a ticker (`AAPL`, `NVDA`) or topic (`Gold`, `Interest Rates`)
3. Run your first news fetch:
   ```bash
   docker exec intelligence python ingestor.py
   ```
4. Articles appear in 1–2 minutes. The scheduler takes over automatically from here.

See `config/starter_topics.json` for a curated list of tickers, topics, and people to follow.

**Stop / restart**

```bash
docker compose down    # stop (your data is preserved)
docker compose up -d   # start again
```

---

## Schedule

The engine runs automatically on weekdays:

| Time | Task |
|------|------|
| 7:00 AM | Ingest new articles |
| 8:00 AM | Regenerate AI briefings |
| 12:00 PM | Ingest new articles |
| 2:00 PM | Regenerate AI briefings |
| 3:00 PM | Ingest new articles |
| 5:00 PM | Regenerate AI briefings |

**Manual triggers** (run any time):

```bash
docker exec intelligence python ingestor.py    # pull fresh articles now
docker exec intelligence python summarizer.py  # regenerate briefings now
```

---

## How It Works

Most news services optimize for engagement. Intelligence optimizes for information density. The pipeline has four stages.

### Stage 1 — Targeted Fetch

The engine builds queries from your tracking list rather than consuming a generic news stream. Each equity ticker gets a dedicated Yahoo Finance RSS feed aggregating Reuters, AP, Motley Fool, Seeking Alpha, and Benzinga specifically for that symbol. Topics, themes, people, and sectors are queried through dynamically-built Google News RSS feeds. Static sources — SEC EDGAR 8-K filings, PR Newswire press releases, CNBC, MarketWatch, and others — run in parallel.

The input is already signal-dense before any filtering begins. See `config/default_sources.json` for the full source list with notes on each.

### Stage 2 — The Deflector (Keyword Relevance Gate)

Every article title and description is checked against your tracked keywords using whole-word matching. An article mentioning "Golden Gate Capital" will not match a search for `Gold`. Articles that don't contain at least one of your target keywords are dropped immediately — before any AI call, at zero cost.

### Stage 3 — AI Analysis

Each article that clears the deflector is sent to Google Gemini for structured analysis. The AI returns a precise JSON object:

| Field | Content |
|-------|---------|
| `dehyped_summary` | 1–2 sentence factual rewrite with all emotional language removed |
| `current_facts` | Specific, verifiable facts: numbers, decisions, completed actions |
| `future_opinions` | Analyst predictions and speculative commentary, cleanly separated |
| `entities` | Companies, funds, indices, and executives named in the article |
| `macro_themes` | Broad economic categories: Interest Rates, AI, Commodities, etc. |
| `event_type` | Classification from a 13-label taxonomy (see below) |
| `hype_score` | 0–100 measure of sensationalism in the writing |
| `impact_score` | 0–100 measure of actual market consequence |

**Event type taxonomy:**

Earnings Report · Earnings Call · Analyst Upgrade · Analyst Downgrade · Price Target Change · Executive Change · Merger & Acquisition · Product Launch · Regulatory Action · Policy Decision · Material Event · Macro Data · General News

**Signal** = `impact_score − hype_score`. Articles with negative Signal are filtered from the Newspaper view. High-impact, low-hype reporting rises. Sensationalist content with no real substance is suppressed.

### Stage 4 — Quality Gate

A final rule-based check decides whether the article is worth storing:

- **Material events always pass** — earnings, analyst calls, executive changes, M&A, and regulatory actions are the events that move asset prices. They are never discarded on signal grounds.
- **Zero facts + negative signal** → dropped. Pure opinion with no informational value.
- **One fact + strongly negative signal** → dropped. Thin recaps that add nothing new.
- **Signal below −25** → dropped unconditionally. No fact density justifies deeply hype-poisoned content.

### Briefings

Three times daily, a separate process reads the last 24 hours of stored articles for each target and sends them to Gemini with one instruction: produce a 4–8 sentence digest, one development per sentence, leading with the most significant event, facts only, no hedging language. This is the briefing card on the Newspaper view — an information-dense snapshot of what actually happened today.

---

## Views

**Newspaper** — Lead story ranked by signal, featured stories, Earnings Calendar, IPO Pipeline, and full AI briefings per ticker and topic.

**Feed** — Scrollable chronological list. Expand any card to see the full de-hyped summary, extracted facts, future projections, and source link.

**Analytics** — Source performance table (pass rate, hype score, dedup rate per outlet), theme mix bar chart, and the Knowledge Graph.

### Knowledge Graph

Three modes showing different dimensions of your information landscape:

| Mode | Primary nodes | Secondary nodes | What it shows |
|------|---------------|-----------------|---------------|
| Focus → Themes | Your tracked targets (gold) | AI-extracted macro themes | What narratives your positions are generating |
| Focus → Sources | Your tracked targets (gold) | News sources | Which outlets are covering which of your holdings |
| Themes → Sources | Macro themes | News sources | Each outlet's editorial focus and topic coverage |

Click any node to zoom in, dim unrelated connections, and see linked articles. Click **← Back** to return to the full graph.

---

## Sources

The default source list is in `config/default_sources.json`. Sources can be enabled or disabled at runtime from the Analytics tab without restarting the engine.

**Current defaults:** Yahoo Finance (per-ticker feeds), PR Newswire, CNBC, MarketWatch, SEC EDGAR (8-K filings), Wall Street Journal, Bloomberg, Benzinga, Seeking Alpha, CoinTelegraph, OilPrice, BBC News, DW News, South China Morning Post.

Note on paywalled sources: Bloomberg and WSJ are included because their headlines and RSS-syndicated summaries are publicly available and often contain enough factual signal. Full article text is not accessed. Pass rates for these sources will be lower than open-access sources.

---

## Starter Targets

`config/starter_topics.json` contains a curated list of tickers, macro topics, sectors, private companies, and notable individuals organized by category. These are suggestions. Use the Tracking panel to add exactly what you follow.

---

## Information Sources and Copyright

Intelligence reads **RSS feeds** — structured data feeds that news organizations publish specifically for automated consumption and redistribution. RSS syndication is the standard mechanism by which publishers make headlines and summaries available to aggregators, readers, and third-party services. Subscribing to an RSS feed is the digital equivalent of reading a newspaper that the publisher placed on a public stand.

**What the engine extracts is facts, not prose.** Facts — specific numbers, named decisions, confirmed actions, dates, prices, and ratings — are not protected by copyright. Copyright protects original creative expression: the particular way a journalist chose to construct a sentence. The AI analysis discards that expression entirely and produces new, independently-written output containing only the factual claims.

In practice:

- The engine reads headlines and RSS-syndicated summaries. Full article text is accessed only when an RSS entry is too short to analyze (under 50 characters), and only to extract factual claims — not to reproduce the writing.
- Every article is rewritten by AI in plain factual language. The output shares no prose with the source.
- No original content is stored in full, redistributed, or published. All output remains on the user's own machine.
- Users are linked to the original source for complete reading.
- The service is personal and private — it has no users other than the person who runs it, no advertising, and no commercial purpose.

This approach mirrors how financial data terminals, news aggregators, and search engine caches have legally operated for decades. The transformation of raw news into structured factual data, retained privately for personal reference, is a well-established use of publicly syndicated information.

---

## Costs

Google Gemini API usage is minimal. A typical day of ingestion across 10–15 targets costs between $0.01 and $0.05. The free tier (1,500 requests/day) covers most personal installations. Current usage is shown in the engine status bar at the top of every page.

---

## Troubleshooting

**Start here:** `docker logs intelligence` shows everything happening inside the container — startup messages, API calls, errors. Always check this first.

**"Cannot connect to Docker daemon" or "command not found: docker"**
Docker Desktop is not running. Open it from your Applications folder, wait for the whale icon in the menu bar to stop animating, then try again.

**"This site can't be reached" at localhost:8001**
The container may not have started. Run `docker compose logs` to see why. Common cause: another program is already using port 8001. Check with `lsof -i :8001`.

**No articles after running the ingestor**
You need at least one target before the ingestor has anything to fetch. Open the app, click **✎ Edit** in the Tracking panel, add a ticker or topic, then run `docker exec intelligence python ingestor.py` again.

**"GEMINI_API_KEY is not set" in the logs**
Your `.env` file is missing or the key is still the placeholder. Check the file contains `GEMINI_API_KEY=AIza...` (your real key). Then restart: `docker compose restart`.

**Verify everything is working**
```bash
curl http://localhost:8001/health
```
Returns `{"status":"ok","api_key":"configured","db":"exists"}` when fully operational.

**Summaries are stale**
Force a refresh: `docker exec intelligence python summarizer.py`

**Earnings Calendar empty**
Requires at least one Ticker-type target. The calendar pulls live data from Yahoo Finance on each page load.

**Container keeps crashing**
`docker logs intelligence` will show the error. The most common cause after initial setup is a missing or invalid API key.
