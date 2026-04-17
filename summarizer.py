"""
Daily Company Briefing Summarizer
==================================
For each Ticker target, reads all matched articles from the last 24 hours and
asks Gemini to write a single, investor-grade paragraph that:
  - Clearly separates confirmed facts from analyst projections / conjecture
  - Covers all material dimensions (earnings, ratings, leadership, regulatory, macro)
  - Says something honest when there's nothing to say

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
DB_PATH  = Path(__file__).parent / "intelligence.db"
MODEL    = "gemini-2.5-flash"

COST_INPUT  = 0.000000075   # $ per input token
COST_OUTPUT = 0.00000030    # $ per output token


# ---------------------------------------------------------------------------
# Gemini output schema
# ---------------------------------------------------------------------------

class TickerBriefing(BaseModel):
    paragraph: str = Field(
        description=(
            "One paragraph (3-6 sentences) written for an investor. "
            "Clearly distinguish facts ('the company reported...', 'shares fell X%...') "
            "from analyst opinions and projections ('analysts expect...', 'the market anticipates...'). "
            "Cover all significant dimensions present in the articles. "
            "If nothing material happened, say so plainly and concisely. "
            "Do not start with the company name or ticker symbol."
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
            paragraph           TEXT NOT NULL,
            sentiment           TEXT DEFAULT "Neutral",
            has_material_events INTEGER DEFAULT 0,
            key_facts           TEXT DEFAULT "[]",
            article_count       INTEGER DEFAULT 0,
            generated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def get_ticker_targets(cursor):
    """Return list of {id, ticker, keywords[]} for all Ticker target locks."""
    cursor.execute('''
        SELECT tl.id, tl.target_value,
               GROUP_CONCAT(tk.keyword, "||") as kw_blob
        FROM target_locks tl
        LEFT JOIN target_keywords tk ON tk.target_lock_id = tl.id
        WHERE tl.target_type = "Ticker"
        GROUP BY tl.id
        ORDER BY tl.target_value
    ''')
    results = []
    for row in cursor.fetchall():
        kws = [k.strip() for k in (row['kw_blob'] or '').split('||') if k.strip()]
        results.append({'ticker': row['target_value'], 'keywords': kws})
    return results


def get_recent_articles(cursor, ticker: str, hours: int = 24):
    """Return articles from the last `hours` that are matched to this ticker."""
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')

    # matched_targets is a JSON array; use json_each for a proper contains check
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
        LIMIT 12
    ''', (since, ticker))
    return cursor.fetchall()


def log_ai_usage(cursor, response, request_type: str):
    if not (hasattr(response, 'usage_metadata') and response.usage_metadata):
        return
    p = response.usage_metadata.prompt_token_count or 0
    c = response.usage_metadata.candidates_token_count or 0
    t = response.usage_metadata.total_token_count or 0
    cost = (p * COST_INPUT) + (c * COST_OUTPUT)
    latency_ms = 0  # already tracked by caller
    cursor.execute('''
        INSERT INTO ai_usage_logs
            (model_id, request_type, prompt_tokens, completion_tokens,
             total_tokens, estimated_cost_usd, latency_ms, status_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (MODEL, request_type, p, c, t, cost, latency_ms, 200))


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def _company_label(ticker: str, keywords: list[str]) -> str:
    """Pick the most readable company name from keyword list, fall back to ticker."""
    candidates = [k for k in keywords if k.lower() != ticker.lower() and len(k) > 2]
    if not candidates:
        return ticker
    # Prefer the longest keyword that looks like a real name (no special chars)
    real_names = [k for k in candidates if re.match(r'^[a-z0-9& ]+$', k, re.I)]
    pool = real_names or candidates
    return max(pool, key=len).title()


def _build_article_context(articles) -> str:
    blocks = []
    for a in articles:
        facts    = json.loads(a['current_facts'])   if a.get('current_facts')   else []
        opinions = json.loads(a['future_opinions'])  if a.get('future_opinions') else []
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


def generate_ticker_briefing(client, ticker: str, keywords: list[str], articles) -> dict:
    """Call Gemini and return a TickerBriefing dict. Handles zero-article case locally."""
    company = _company_label(ticker, keywords)

    if not articles:
        return {
            'paragraph': (
                f"No articles matched {company} ({ticker}) in the last 24 hours. "
                "Nothing worth flagging today."
            ),
            'sentiment': 'Neutral',
            'has_material_events': False,
            'key_facts': [],
        }

    context = _build_article_context(articles)
    prompt = f"""You are a financial intelligence analyst writing a concise daily briefing paragraph for a portfolio investor.

Company: {company} ({ticker})
Coverage window: last 24 hours
Source articles: {len(articles)}

--- ARTICLES ---
{context}
--- END ARTICLES ---

Instructions:
1. Write ONE paragraph of 3-6 sentences summarising what happened to {ticker} today.
2. Clearly label facts vs. conjecture:
   - Facts: "the company reported...", "shares rose/fell X%...", "the board announced..."
   - Conjecture: "analysts expect...", "the market anticipates...", "one firm projects..."
3. Cover all dimensions present: earnings/results, analyst ratings/price targets, leadership, regulatory, macro exposure.
4. If nothing material happened, say so plainly — e.g. "No material developments today. Analyst sentiment remains broadly constructive."
5. Do NOT begin with the company name or ticker as the opening word.
6. No bullet points. One flowing paragraph only.
"""

    t0 = time.time()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TickerBriefing,
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
    result['_response'] = response   # carry response for usage logging
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

    targets = get_ticker_targets(cursor)
    if not targets:
        logging.info("No Ticker targets configured — nothing to summarise.")
        conn.close()
        return

    client = genai.Client(api_key=API_KEY)
    logging.info(f"Generating briefings for {len(targets)} ticker(s)...")

    for t in targets:
        ticker   = t['ticker']
        keywords = t['keywords']
        articles = get_recent_articles(cursor, ticker)
        logging.info(f"  {ticker}: {len(articles)} article(s) in last 24h")

        try:
            result   = generate_ticker_briefing(client, ticker, keywords, articles)
            response = result.pop('_response', None)

            if response:
                log_ai_usage(cursor, response, 'company-briefing')

            cursor.execute('''
                INSERT INTO company_summaries
                    (target_value, paragraph, sentiment, has_material_events,
                     key_facts, article_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                result['paragraph'],
                result.get('sentiment', 'Neutral'),
                1 if result.get('has_material_events') else 0,
                json.dumps(result.get('key_facts', [])),
                len(articles),
            ))
            conn.commit()
            logging.info(f"  {ticker}: stored ({result.get('sentiment')} / "
                         f"material={result.get('has_material_events')})")

        except Exception as e:
            logging.error(f"  {ticker}: briefing failed — {e}")

        time.sleep(1.5)   # polite pause between Gemini calls

    conn.close()
    logging.info("Briefing generation complete.")


if __name__ == "__main__":
    main()
