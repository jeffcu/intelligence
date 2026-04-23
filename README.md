# Intelligence — Private News Engine

A self-hosted financial and world news service that reads dozens of sources, strips hype and opinion, and surfaces only what actually matters — classified, scored, and summarized by AI. No ads, no engagement algorithms, no clickbait.

---

## Quick Start

**Prerequisites:** Docker Desktop installed ([docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop))

**1. Create your API key file.**
In the same folder as `docker-compose.yml`, create a file named `.env` containing:

```
GEMINI_API_KEY=your_key_here
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com). The free tier is sufficient for personal use.

**2. Start the container.**

```bash
docker compose up -d
```

First run downloads the image (~500MB). Subsequent starts are instant.

**3. Open your browser.**

```
http://localhost:8001
```

**4. Add your tickers and topics.**

Click **✎ Edit** in the Tracking panel. Add stock tickers (`AAPL`, `NVDA`, `MSFT`) as type **Ticker**, or topics like `Gold`, `Interest Rates`, `Elon Musk` as their respective types.

**5. Run the ingestor to pull your first batch of news.**

```bash
docker exec intelligence python ingestor.py
```

After a minute or two, articles appear in the feed. From this point the scheduler runs automatically.

**6. Stop / restart.**

```bash
docker compose down    # stop
docker compose up -d   # start again (your data is preserved)
```

---

## Schedule

The engine runs on its own internal schedule (weekdays):

| Time | Task |
|------|------|
| 7:00 AM | Ingest new articles |
| 8:00 AM | Regenerate AI summaries |
| 12:00 PM | Ingest new articles |
| 2:00 PM | Regenerate AI summaries |
| 3:00 PM | Ingest new articles |
| 5:00 PM | Regenerate AI summaries |

---

## How the Engine Works

Most news services optimize for engagement — they surface whatever makes you click, share, or feel strong emotions. Intelligence optimizes for information density: every article that reaches your feed has been verified to contain real facts, measured against its sensationalism, and classified by event type before you see it. The pipeline has four stages.

### Stage 1 — Targeting and Fetch

The engine does not fetch a generic news stream. It constructs targeted queries from your tracking list. For each equity ticker you add (`AAPL`, `NVDA`, etc.), it builds a dedicated Yahoo Finance RSS feed that aggregates Reuters, AP, Motley Fool, Seeking Alpha, and Benzinga specifically for that ticker. For topics and themes, it builds Google News RSS queries grouped by type — companies, macro topics, people, sectors — chunked to stay precise.

This means the raw input is already signal-dense before any filtering begins. You are not sifting through general news hoping something relevant appears; the fetch layer is constructed specifically around what you said you care about.

### Stage 2 — The Deflector (Keyword Relevance Gate)

Every article title and description is checked against your target keywords using whole-word matching. An article about a company called "Golden Gate Capital" will not match a search for `Gold`. The deflector is fast and runs before any AI processing — articles that don't contain at least one of your target keywords in their text are dropped immediately, saving both time and API cost.

Only articles that pass keyword relevance proceed to the AI stage.

### Stage 3 — AI Analysis and Tagging

This is the core of the engine. Each article that clears the deflector is sent to Google Gemini for structured analysis. The AI is given the article's title and description and instructed to return a precise JSON object with the following fields:

**`dehyped_summary`** — A 1–2 sentence factual rewrite of the article with all emotional language, superlatives, and value judgments removed. "Nvidia's STUNNING earnings OBLITERATE expectations in massive beat!" becomes "Nvidia reported Q3 earnings of $X per share, exceeding consensus estimates of $Y."

**`current_facts`** — A list of things that are actually true and verifiable right now: specific numbers, confirmed decisions, completed actions.

**`future_opinions`** — Separated cleanly from facts: analyst predictions, management guidance, speculative commentary. These are shown in the feed but visually distinguished, so you always know what has happened versus what someone thinks might happen.

**`entities`** — Major companies, funds, and indices named in the article.

**`macro_themes`** — Broad economic categories the article belongs to: Interest Rates, Commodities, Central Banks, Crypto, etc.

**`event_type`** — A classification from a fixed 13-label taxonomy:

| Label | Meaning |
|-------|---------|
| Earnings Report | Quarterly/annual results, EPS, revenue |
| Earnings Call | Management guidance and forward outlook |
| Analyst Upgrade | Rating raised, buy/outperform initiated |
| Analyst Downgrade | Rating cut, sell/underperform |
| Price Target Change | Analyst raises or lowers a price target |
| Executive Change | CEO/CFO departure, appointment, resignation |
| Merger & Acquisition | Deal announced, completed, or terminated |
| Product Launch | New product, service, or platform |
| Regulatory Action | FDA ruling, SEC action, antitrust, fine |
| Policy Decision | Central bank rate decision, government policy |
| Material Event | Any other company-specific market-moving event |
| Macro Data | Economic indicators: CPI, jobs report, GDP |
| General News | Background, opinion, or low-impact coverage |

**`hype_score`** (0–100) — How sensationalist the writing is. A straightforward Reuters wire story about a rate decision scores near 0. A Seeking Alpha piece titled "This One Chart Shows Why NVDA Is Going to $2,000" scores near 90.

**`impact_score`** (0–100) — How much this event actually matters in market terms. A company reporting earnings that beat by 40 cents and raising guidance scores high. A podcast transcript summarizing last week's news scores low.

The engine computes a **Signal** for every article: `impact_score − hype_score`. Only articles with a non-negative Signal appear in the feed. High-impact, low-hype reporting rises; sensationalist noise with no real content is filtered out.

### Stage 4 — The Quality Gate

After AI classification, a final rule-based check decides whether the article is worth storing. Material events (earnings, executive changes, analyst calls, M&A, regulatory actions) always pass regardless of score — these are exactly the events you track. For everything else, three rejection rules apply:

- **Zero extracted facts + negative signal** → dropped. The AI found nothing concrete and the signal is net negative. This is pure opinion or market color with no informational value.
- **One fact + strongly negative signal** → dropped. Thin meta-articles, recaps, and "here's what happened last week" summaries don't add new information.
- **Signal below −25** → dropped unconditionally. No amount of facts justifies publishing deeply hype-poisoned content.

Articles that pass all four stages are stored, tagged, and appear in your feed. The source performance table in the Analytics tab shows exactly how many articles each source sends versus how many survive — a direct measure of source quality.

### Summaries

Three times a day, a separate process reads the last 24 hours of stored articles for each target you track and sends them to Gemini with a single instruction: produce a punchy 4–8 sentence digest, one development per sentence, leading with the most significant event, facts only, no hedging language. The result is the briefing card you see on the Newspaper view — an information-dense snapshot of what actually happened to that ticker or topic today.

---

## Why Tagging Makes It Work

Traditional news aggregators show you everything that mentions a keyword. Intelligence shows you only what is about that keyword and has something concrete to say.

The AI tagging layer creates a structured data record for each article rather than treating it as a blob of text. Once an article is tagged, the system can answer precise questions: Is this article primarily about AAPL, or does it merely mention Apple in passing? Is this claim a confirmed fact or an analyst opinion? Is this a material event that moves markets, or general commentary? Did the writer use 15 exclamation points to compensate for having nothing to say?

Because every article carries the same structured schema — facts separated from opinions, event type classified, scores computed — the display layer can make intelligent decisions about what to show and how. The Newspaper front page leads with the highest signal-to-hype article. Material event badges (Earnings, Leadership change, M&A) appear only when the AI confirmed the article is actually about that event, not just adjacent to it. Articles older than 24 hours are visually dimmed, because yesterday's analyst note is not today's news.

The knowledge graph in the Analytics tab is a direct byproduct of tagging: every entity the AI extracted from every article becomes a node, and every article that mentions two entities together creates a weighted link between them. The graph shows you who is connected to what, derived entirely from what has been written about in the last 150 articles — a real-time map of the information space around your targets.

---

## Views

**Newspaper** — Default view. Lead story ranked by signal, featured stories, full AI briefings per ticker and topic, earnings calendar and IPO pipeline always visible.

**Intelligence Feed** — Scrollable list of every article in chronological/signal order. Expand any card to see the full de-hyped summary, extracted facts, future projections, and source link.

**Analytics** — Source performance league table (which feeds produce the most signal vs. noise) and the entity knowledge graph.

---

## Costs

Google Gemini API usage is minimal. A typical day of ingestion across 10–15 targets costs between $0.01 and $0.05. The free tier (1,500 requests/day) is sufficient unless you track a very large number of targets. Your usage is shown in the Intelligence Engine bar at the top of every page.

---

## Troubleshooting

**No articles appearing after running the ingestor:**
Make sure you have added at least one target in the Tracking panel before running the ingestor. The engine only fetches feeds for targets you have defined.

**API error / offline banner:**
The container may not have started correctly. Run `docker compose logs` to see what happened.

**Summaries are stale:**
Summaries regenerate three times daily. To force an immediate refresh: `docker exec intelligence python summarizer.py`

**Run the ingestor manually at any time:**
`docker exec intelligence python ingestor.py`
