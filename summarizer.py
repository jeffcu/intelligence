"""
Daily Briefing Summarizer
==========================
Generates punchy digest paragraphs for every tracked target:
  - Ticker targets  → company briefings (what happened to this stock today)
  - Topic targets   → theme briefings  (what happened in this macro / sector / theme)

Each paragraph is 4-8 short sentences, one development per sentence, leading with
the most significant news. Facts stated directly; conjecture gets "expected /
anticipated / analysts project".

Run automatically at 2pm by news_scheduler.py, or manually:
    python summarizer.py
"""

import sqlite3
import json
import os
import re
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
API_KEY  = os.getenv("GEMINI_API_KEY")
DB_PATH  = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "intelligence.db")))
MODEL    = "gemini-2.5-flash"

COST_INPUT  = 0.000000075   # $ per input token
COST_OUTPUT = 0.00000030    # $ per output token


# ---------------------------------------------------------------------------
# Gemini output schema  (shared by ticker + topic briefings)
# ---------------------------------------------------------------------------

class Briefing(BaseModel):
    paragraph: str = Field(
        description=(
            "4-8 short, punchy sentences — one distinct development per sentence. "
            "Lead with the biggest news. "
            "Use plain natural language: 'Earnings tomorrow.', 'CEO joins Ford board.', "
            "'Partnership with Amazon for $500B announced.', 'Analysts raising price targets.'. "
            "Conjecture gets a natural qualifier: 'expected', 'analysts project', 'anticipated'. "
            "No flowery investor language, no 'it is worth noting', no lengthy preamble. "
            "If nothing material happened, say so in one short sentence. "
            "CRITICAL FORMATTING RULE: Within each sentence, wrap the core signal phrase "
            "in **double asterisks**. Exactly one highlight per sentence. "
            "The highlight MUST follow these actor rules: "
            "(1) PERSONNEL — always include the person's name AND the change: "
            "'**Tim Cook steps down as CEO**', '**Jane Smith joins board**', '**CFO John Lee resigns**'. "
            "Never highlight just the role or just the action without the name. "
            "(2) PARTNERSHIPS / DEALS / INVESTMENTS — always include both parties AND the action: "
            "'**OpenAI partners with Amazon**', '**Oppenheimer acquires Nvidia position**', "
            "'**Apple acquires Beats for $3B**', '**SoftBank invests $500M in OpenAI**'. "
            "Never highlight only one party or only the dollar amount. "
            "(3) FINANCIAL RESULTS / ANALYST ACTIONS — include the actor and the key number: "
            "'**Goldman raises price target to $210**', '**Earnings beat by $0.12**', "
            "'**Revenue missed by 4%**'. "
            "(4) MACRO / PRODUCT / REGULATORY — highlight the subject and action together: "
            "'**Fed holds rates steady**', '**TPU v5 launches in Q3**', '**SEC approves Bitcoin ETF**'. "
            "The ** markers must appear literally in the output string."
        )
    )
    sentiment: str = Field(
        description="One word: Positive, Negative, Neutral, or Mixed"
    )
    has_material_events: bool = Field(
        description="True if any earnings, rating changes, executive changes, M&A, or regulatory action is present"
    )
    key_facts: list[str] = Field(
        description="Up to 4 specific, verifiable facts extracted from the articles. Empty list if none."
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_summaries_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_summaries (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            target_value        TEXT NOT NULL,
            target_type         TEXT DEFAULT "Ticker",
            paragraph           TEXT NOT NULL,
            sentiment           TEXT DEFAULT "Neutral",
            has_material_events INTEGER DEFAULT 0,
            key_facts           TEXT DEFAULT "[]",
            article_count       INTEGER DEFAULT 0,
            generated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migrate older schema that lacks target_type
    try:
        cursor.execute('ALTER TABLE company_summaries ADD COLUMN target_type TEXT DEFAULT "Ticker"')
    except sqlite3.OperationalError:
        pass  # Column already exists


def _is_equity_ticker(value: str) -> bool:
    """Return False for CUSIPs, numeric fund codes, and mutual fund tickers.
    Mutual funds follow the US convention of exactly 5 chars ending in X.
    ETFs (SPY, VOO, QQQ) and equities (AAPL, GOOGL) are kept.
    """
    if not value:
        return False
    if value[0].isdigit():          # CUSIPs / numeric fund codes (91282CFU0, 9999227)
        return False
    if len(value) >= 8:             # Long identifiers
        return False
    if len(value) == 5 and value.upper().endswith('X'):  # SMLPX, PYMPX, HGIFX…
        return False
    return True


def get_ticker_targets(cursor):
    """Return [{ticker, keywords}] for all equity Ticker target locks."""
    cursor.execute('''
        SELECT tl.id, tl.target_value,
               GROUP_CONCAT(tk.keyword, "||") AS kw_blob
        FROM target_locks tl
        LEFT JOIN target_keywords tk ON tk.target_lock_id = tl.id
        WHERE tl.target_type = "Ticker"
        GROUP BY tl.id
        ORDER BY tl.target_value
    ''')
    results = []
    for row in cursor.fetchall():
        ticker = row['target_value']
        if not _is_equity_ticker(ticker):
            logging.debug(f"  Skipping non-equity identifier: {ticker}")
            continue
        kws = [k.strip() for k in (row['kw_blob'] or '').split('||') if k.strip()]
        results.append({'ticker': ticker, 'keywords': kws})
    return results


def get_topic_targets(cursor):
    """Return [{topic, target_type}] for all non-Ticker target locks."""
    cursor.execute('''
        SELECT tl.id, tl.target_type, tl.target_value
        FROM target_locks tl
        WHERE tl.target_type != "Ticker"
        ORDER BY tl.target_value
    ''')
    return [
        {'topic': row['target_value'], 'target_type': row['target_type']}
        for row in cursor.fetchall()
    ]


def get_recent_articles_by_target(cursor, target_value: str, hours: int = 24):
    """Return articles from the last `hours` matched to this target value."""
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')
    cursor.execute('''
        SELECT title, dehyped_summary, current_facts, future_opinions,
               event_type, impact_score, hype_score, source, published_at
        FROM articles
        WHERE published_at >= ?
          AND EXISTS (
              SELECT 1 FROM json_each(COALESCE(matched_targets, "[]"))
              WHERE value = ?
          )
        ORDER BY impact_score DESC
        LIMIT 15
    ''', (since, target_value))
    return cursor.fetchall()


def log_ai_usage(cursor, response, request_type: str):
    if not (hasattr(response, 'usage_metadata') and response.usage_metadata):
        return
    p = response.usage_metadata.prompt_token_count or 0
    c = response.usage_metadata.candidates_token_count or 0
    t = response.usage_metadata.total_token_count or 0
    cost = (p * COST_INPUT) + (c * COST_OUTPUT)
    cursor.execute('''
        INSERT INTO ai_usage_logs
            (model_id, request_type, prompt_tokens, completion_tokens,
             total_tokens, estimated_cost_usd, latency_ms, status_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (MODEL, request_type, p, c, t, cost, 0, 200))


def _store_summary(cursor, target_value: str, target_type: str, result: dict, article_count: int):
    cursor.execute('''
        INSERT INTO company_summaries
            (target_value, target_type, paragraph, sentiment, has_material_events,
             key_facts, article_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        target_value,
        target_type,
        result['paragraph'],
        result.get('sentiment', 'Neutral'),
        1 if result.get('has_material_events') else 0,
        json.dumps(result.get('key_facts', [])),
        article_count,
    ))


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _company_label(ticker: str, keywords: list[str]) -> str:
    candidates = [k for k in keywords if k.lower() != ticker.lower() and len(k) > 2]
    if not candidates:
        return ticker
    real_names = [k for k in candidates if re.match(r'^[a-z0-9& ]+$', k, re.I)]
    pool = real_names or candidates
    return max(pool, key=len).title()


def _build_article_context(articles) -> str:
    blocks = []
    for a in articles:
        facts    = json.loads(a['current_facts'])   if a['current_facts']   else []
        opinions = json.loads(a['future_opinions'])  if a['future_opinions'] else []
        block = (
            f"[{a['event_type']} | Impact {a['impact_score']} | {a['source']}]\n"
            f"Title: {a['title']}\n"
            f"Summary: {a['dehyped_summary'] or ''}"
        )
        if facts:
            block += f"\nFacts: {' | '.join(facts[:4])}"
        if opinions:
            block += f"\nProjections: {' | '.join(opinions[:2])}"
        blocks.append(block)
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Briefing generation — Ticker
# ---------------------------------------------------------------------------

def generate_ticker_briefing(client, ticker: str, keywords: list[str], articles) -> dict:
    company = _company_label(ticker, keywords)

    if not articles:
        return {
            'paragraph': f"Nothing in the feed for {company} in the last 24 hours.",
            'sentiment': 'Neutral',
            'has_material_events': False,
            'key_facts': [],
        }

    context = _build_article_context(articles)
    prompt = f"""You are writing a quick daily digest for a portfolio investor who wants to know what happened with {ticker} ({company}) in the last 24 hours.

Company: {company} ({ticker})
Source articles: {len(articles)}

--- ARTICLES ---
{context}
--- END ARTICLES ---

Write 4-8 short, punchy sentences. One distinct development per sentence. Lead with the most significant news.

Style guide — write EXACTLY like these examples:
  "Earnings report tomorrow before market open."
  "Analysts at Goldman raised price target from $180 to $210."
  "Strategic partnership with Amazon announced, $500B in contracted sales."
  "CEO joining Ford's board of directors."
  "Lawsuit over union practices expected to have minimal financial impact."
  "Shares fell 3.2% on broader market sell-off."

Rules:
- Confirmed facts stated directly. Projections and expectations get "expected", "analysts project", "anticipated", "forecast".
- No bullet points — short sentences only.
- Do NOT start with the company name or ticker symbol as the opening word.
- No "it is worth noting", no formal investor-ese.
- If nothing material happened: "Nothing significant today — analyst sentiment broadly steady."
- HIGHLIGHT RULE: Wrap the core signal in **double asterisks** — one per sentence, no exceptions. Always include the actor WITH the action: personnel → "**Tim Cook steps down as CEO**" not "**steps down as CEO**"; deals/partnerships → "**OpenAI partners with Amazon**" not "**partnership with Amazon**"; analyst moves → "**Goldman raises target to $210**"; macro/product → "**Fed holds rates steady**". The ** must appear literally in the string.
"""

    t0 = time.time()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Briefing,
            temperature=0.15,
        ),
    )
    elapsed_ms = int((time.time() - t0) * 1000)
    logging.info(f"    Gemini responded in {elapsed_ms}ms")

    raw = response.text.strip()
    if raw.startswith('```json'):
        raw = raw[7:]
    if raw.endswith('```'):
        raw = raw[:-3]
    result = json.loads(raw.strip())
    result['_response'] = response
    return result


# ---------------------------------------------------------------------------
# Briefing generation — Topic
# ---------------------------------------------------------------------------

def generate_topic_briefing(client, topic: str, articles) -> dict:
    if not articles:
        return {
            'paragraph': f"Nothing significant on {topic} in the last 24 hours.",
            'sentiment': 'Neutral',
            'has_material_events': False,
            'key_facts': [],
        }

    context = _build_article_context(articles)
    prompt = f"""You are writing a quick daily digest about the topic "{topic}" for a portfolio investor.

Topic: {topic}
Source articles: {len(articles)}

--- ARTICLES ---
{context}
--- END ARTICLES ---

Write 4-8 short, punchy sentences covering the key developments on this topic today. One distinct development per sentence. Lead with the most significant news.

Style guide — write EXACTLY like these examples:
  "Gold hit a new all-time high above $3,300/oz."
  "Bitcoin surged past $95,000 on renewed institutional buying."
  "Trump signed an executive order targeting tech sector tariffs."
  "Fed officials signaled rates could stay higher for longer."
  "Crude oil fell 2.1% on demand concerns from China slowdown data."

Rules:
- Confirmed facts stated directly. Projections and expectations get "expected", "anticipated", "forecast".
- No bullet points — short sentences only.
- Do NOT start with the topic name as the opening word.
- No "it is worth noting", no formal investor-ese.
- If nothing material happened: "Quiet day for {topic} — no major developments."
- HIGHLIGHT RULE: Wrap the core signal in **double asterisks** — one per sentence, no exceptions. Always include the actor WITH the action: personnel → "**Tim Cook steps down as CEO**" not "**steps down as CEO**"; deals/partnerships → "**OpenAI partners with Amazon**" not "**partnership with Amazon**"; analyst moves → "**Goldman raises target to $210**"; macro/product → "**Fed holds rates steady**". The ** must appear literally in the string.
"""

    t0 = time.time()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Briefing,
            temperature=0.15,
        ),
    )
    elapsed_ms = int((time.time() - t0) * 1000)
    logging.info(f"    Gemini responded in {elapsed_ms}ms")

    raw = response.text.strip()
    if raw.startswith('```json'):
        raw = raw[7:]
    if raw.endswith('```'):
        raw = raw[:-3]
    result = json.loads(raw.strip())
    result['_response'] = response
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not API_KEY:
        logging.error("GEMINI_API_KEY not found — cannot generate summaries.")
        return

    conn = _get_conn()
    cursor = conn.cursor()
    ensure_summaries_table(cursor)
    conn.commit()

    client = genai.Client(api_key=API_KEY)

    # ── Ticker briefings ────────────────────────────────────────────────────
    ticker_targets = get_ticker_targets(cursor)
    logging.info(f"Generating briefings for {len(ticker_targets)} equity ticker(s)...")

    for t in ticker_targets:
        ticker   = t['ticker']
        keywords = t['keywords']
        articles = get_recent_articles_by_target(cursor, ticker)
        logging.info(f"  {ticker}: {len(articles)} article(s) in last 24h")

        try:
            result   = generate_ticker_briefing(client, ticker, keywords, articles)
            response = result.pop('_response', None)
            if response:
                log_ai_usage(cursor, response, 'ticker-briefing')
            _store_summary(cursor, ticker, 'Ticker', result, len(articles))
            conn.commit()
            logging.info(f"  {ticker}: stored ({result.get('sentiment')} / material={result.get('has_material_events')})")
        except Exception as e:
            logging.error(f"  {ticker}: briefing failed — {e}")

        time.sleep(1.5)

    # ── Topic briefings ─────────────────────────────────────────────────────
    topic_targets = get_topic_targets(cursor)
    logging.info(f"Generating briefings for {len(topic_targets)} topic(s)...")

    for t in topic_targets:
        topic       = t['topic']
        target_type = t['target_type']
        articles    = get_recent_articles_by_target(cursor, topic)
        logging.info(f"  [{target_type}] {topic}: {len(articles)} article(s) in last 24h")

        try:
            result   = generate_topic_briefing(client, topic, articles)
            response = result.pop('_response', None)
            if response:
                log_ai_usage(cursor, response, 'topic-briefing')
            _store_summary(cursor, topic, target_type, result, len(articles))
            conn.commit()
            logging.info(f"  {topic}: stored ({result.get('sentiment')} / material={result.get('has_material_events')})")
        except Exception as e:
            logging.error(f"  {topic}: topic briefing failed — {e}")

        time.sleep(1.5)

    conn.close()
    logging.info("Briefing generation complete.")


if __name__ == "__main__":
    main()
