import feedparser
import sqlite3
import json
import os
import re
import time
import logging
import requests
import chromadb
import markdownify
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load Environment Life Support
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# DB & Vector Coordinates
DB_PATH     = Path(os.getenv("DB_PATH",     str(Path(__file__).parent / "intelligence.db")))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", str(Path(__file__).parent / "chroma_db")))

# Pydantic Structural Containment Field
class ArticleAnalysis(BaseModel):
    dehyped_summary: str = Field(description="A purely objective, factual 1-2 sentence summary without emotional adjectives.")
    current_facts: list[str] = Field(description="List of facts happening right now.")
    future_opinions: list[str] = Field(description="List of predictions, analyst guesses, or hype.")
    entities: list[str] = Field(description="List of extracted key entities, prioritizing major companies and macro indices.")
    macro_themes: list[str] = Field(description="List of broad macro themes (e.g., Interest Rates, Crypto, Commodities, Central Banks).")
    event_type: str = Field(description=(
        "Classify the primary event type using EXACTLY one of these labels: "
        "'Earnings Report' (quarterly/annual results, EPS, revenue beats/misses), "
        "'Earnings Call' (transcript, guidance, forward outlook from management), "
        "'Analyst Upgrade' (rating raised, buy/outperform initiated), "
        "'Analyst Downgrade' (rating cut, sell/underperform), "
        "'Price Target Change' (analyst raises or lowers price target), "
        "'Executive Change' (CEO/CFO/board departure, appointment, resignation), "
        "'Merger & Acquisition' (deal announced, completed, or terminated), "
        "'Product Launch' (new product, service, or platform announced), "
        "'Regulatory Action' (FDA ruling, SEC action, antitrust, fine), "
        "'Policy Decision' (central bank rate decision, government policy), "
        "'Material Event' (any other company-specific event with direct market impact), "
        "'Macro Data' (economic indicators: CPI, jobs report, GDP), "
        "'General News' (background, opinion, or low-impact coverage)."
    ))
    hype_score: int = Field(description="0-100 integer evaluating sensationalism.")
    impact_score: int = Field(description="0-100 integer evaluating actual material market consequence based on ISQ framework.")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Core articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            summary TEXT,
            dehyped_summary TEXT,
            current_facts TEXT,
            future_opinions TEXT,
            entities TEXT,
            macro_themes TEXT,
            event_type TEXT,
            hype_score INTEGER,
            impact_score INTEGER,
            source TEXT,
            link TEXT,
            published_at TEXT,
            matched_targets TEXT
        )
    ''')

    # AI cost telemetry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider TEXT DEFAULT 'google_gemini',
            model_id TEXT,
            request_type TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd REAL,
            latency_ms INTEGER,
            status_code INTEGER
        )
    ''')

    # Per-source performance counters
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS source_performance (
            source_name TEXT PRIMARY KEY,
            total_articles_ingested INTEGER DEFAULT 0,
            redundant_articles_chopped INTEGER DEFAULT 0,
            deflected_articles INTEGER DEFAULT 0,
            quality_rejected_articles INTEGER DEFAULT 0,
            average_hype_score REAL DEFAULT 0.0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Dynamic source governance registry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS source_registry (
            source_name TEXT PRIMARY KEY,
            feed_url TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            source_type TEXT DEFAULT 'rss',
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Target locks: what the system watches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_value TEXT UNIQUE NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Keyword expansion per target (powers the Level 1 Deflector)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_lock_id INTEGER NOT NULL REFERENCES target_locks(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(target_lock_id, keyword)
        )
    ''')

    # --- Seed static RSS sources ---
    default_sources = [
        ('Yahoo Finance',          'https://finance.yahoo.com/news/rssindex',            1, 'rss'),
        ('Benzinga',               'https://www.benzinga.com/feed',                      1, 'rss'),
        ('CoinTelegraph',          'https://cointelegraph.com/rss',                      1, 'rss'),
        ('OilPrice',               'https://oilprice.com/rss/main',                      1, 'rss'),
        ('Wall St Journal',        'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',      1, 'rss'),
        ('Bloomberg',              'https://feeds.bloomberg.com/markets/news.rss',       1, 'rss'),
        ('Seeking Alpha',          'https://seekingalpha.com/feed.xml',                  1, 'rss'),
        ('South China Morning Post','https://www.scmp.com/rss/91/feed',                  1, 'rss'),
        ('DW News',                'https://rss.dw.com/rdf/rss-en-all',                  1, 'rss'),
        ('BBC News',               'http://feeds.bbci.co.uk/news/rss.xml',               1, 'rss'),
        ('SEC EDGAR',              'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom', 1, 'rss'),
        # Wire services and financial press — verified working feeds
        ('PR Newswire',            'https://www.prnewswire.com/rss/news-releases-list.rss',                                              1, 'rss'),
        ('CNBC',                   'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',               1, 'rss'),
        ('MarketWatch',            'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines',                                  1, 'rss'),
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO source_registry (source_name, feed_url, is_active, source_type)
        VALUES (?, ?, ?, ?)
    ''', default_sources)

    # --- Seed default target locks (first run only) ---
    # Only seeds when the table is completely empty so that manually-deleted
    # targets are never resurrected by a subsequent ingestor run.
    cursor.execute("SELECT COUNT(*) FROM target_locks")
    if cursor.fetchone()[0] == 0:
        default_targets = [
            ('Macro',   'Gold'),
            ('Macro',   'Bitcoin'),
            ('Macro',   'Wall Street'),
            ('Macro',   'World Events'),
            ('Person',  'Donald Trump'),
            ('Company', 'Private Companies'),
        ]
        cursor.executemany('''
            INSERT OR IGNORE INTO target_locks (target_type, target_value)
            VALUES (?, ?)
        ''', default_targets)

        default_keywords = {
            'Gold':              ['gold', 'gold price', 'xau', 'precious metals', 'bullion'],
            'Bitcoin':           ['bitcoin', 'btc', 'crypto', 'cryptocurrency', 'blockchain', 'digital assets'],
            'Wall Street':       ['wall street', 's&p 500', 'sp500', 'dow jones', 'nasdaq', 'stock market',
                                  'federal reserve', 'fed', 'equity market', 'interest rate'],
            'World Events':      ['geopolitical', 'war', 'conflict', 'sanctions', 'tariff', 'trade war',
                                  'recession', 'inflation', 'gdp'],
            'Donald Trump':      ['trump', 'donald trump', 'white house', 'executive order', 'maga'],
            'Private Companies': ['private equity', 'ipo', 'venture capital', 'startup', 'unicorn'],
        }
        for target_value, keywords in default_keywords.items():
            cursor.execute("SELECT id FROM target_locks WHERE target_value = ?", (target_value,))
            row = cursor.fetchone()
            if row:
                target_id = row['id']
                for kw in keywords:
                    cursor.execute('''
                        INSERT OR IGNORE INTO target_keywords (target_lock_id, keyword)
                        VALUES (?, ?)
                    ''', (target_id, kw))

    # --- Schema evolution (safe ALTER TABLE for existing DBs) ---
    safe_alters = [
        ("ALTER TABLE articles ADD COLUMN current_facts TEXT",),
        ("ALTER TABLE articles ADD COLUMN future_opinions TEXT",),
        ("ALTER TABLE articles ADD COLUMN entities TEXT",),
        ("ALTER TABLE articles ADD COLUMN macro_themes TEXT",),
        ("ALTER TABLE articles ADD COLUMN event_type TEXT",),
        ("ALTER TABLE articles ADD COLUMN matched_targets TEXT",),
        ("ALTER TABLE source_performance ADD COLUMN deflected_articles INTEGER DEFAULT 0",),
        ("ALTER TABLE source_performance ADD COLUMN quality_rejected_articles INTEGER DEFAULT 0",),
    ]
    for (stmt,) in safe_alters:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Targeting helpers
# ---------------------------------------------------------------------------

def load_active_keywords(cursor):
    """Return a frozenset of all expanded keywords (lowercase) across all targets.
    Used by the Level 1 Deflector for fast O(n) matching."""
    cursor.execute('''
        SELECT LOWER(tk.keyword) as keyword
        FROM target_keywords tk
        JOIN target_locks tl ON tk.target_lock_id = tl.id
    ''')
    return frozenset(row['keyword'] for row in cursor.fetchall())


def load_target_keywords_map(cursor):
    """Return {target_lock_id: [keyword, ...]} for matched_targets computation."""
    cursor.execute("SELECT target_lock_id, LOWER(keyword) as keyword FROM target_keywords")
    result = {}
    for row in cursor.fetchall():
        result.setdefault(row['target_lock_id'], []).append(row['keyword'])
    return result


def load_active_targets(cursor):
    """Return list of all target lock dicts: {id, target_type, target_value}."""
    cursor.execute("SELECT id, target_type, target_value FROM target_locks ORDER BY target_type, target_value")
    return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Level 1 Deflector
# ---------------------------------------------------------------------------

def is_relevant(title, summary, keywords):
    """Return True if the article passes the relevance gate (should be processed).
    Uses whole-word regex matching so 'gold' does not match 'golden'.
    Returns False (deflect) if no keywords are loaded — a safety guard.
    """
    if not keywords:
        return False
    text = (title + ' ' + summary).lower()
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def compute_matched_targets(entities, macro_themes, active_targets, keywords_map, title, summary):
    """After AI extraction, determine which specific targets this article matched.

    Ticker targets use title-only matching to prevent false positives from passing
    mentions. An article about Innventure that mentions NVDA in the body is NOT an
    NVDA article — only articles whose title names the ticker/company count.

    Non-ticker targets (Macro, Person, Company, Subject) use full-text matching
    because a passing reference to "Federal Reserve" or "Donald Trump" anywhere
    in an article is genuinely relevant to those watch topics.

    Returns a list of matched target_value strings.
    """
    title_text = title.lower()
    full_text  = ' '.join([title, summary] + entities + macro_themes).lower()

    matched = []
    for target in active_targets:
        kws = keywords_map.get(target['id'], [])
        # Tickers: title only — the subject must be named up front
        # Everything else: full text is fair game
        search_text = title_text if target['target_type'] == 'Ticker' else full_text
        for kw in kws:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, search_text, re.IGNORECASE):
                matched.append(target['target_value'])
                break  # one keyword match per target is sufficient
    return matched


def is_equity_ticker(value):
    """Return True if the value looks like a tradable equity ticker (1-5 uppercase letters).
    Excludes bond CUSIPs (e.g. 91282CFU0), numeric fund codes (9999227), etc.
    """
    return bool(re.match(r'^[A-Z]{1,5}$', value))


def build_ticker_rss_feeds(active_targets):
    """Build per-ticker Yahoo Finance RSS feeds for all equity Ticker targets.
    Yahoo Finance aggregates Reuters, AP, Motley Fool, Seeking Alpha, Benzinga
    per ticker — the highest-signal source for earnings, upgrades, and price targets.
    Returns list of (source_name, feed_url) tuples.
    """
    feeds = []
    for t in active_targets:
        if t['target_type'] == 'Ticker' and is_equity_ticker(t['target_value']):
            ticker = t['target_value']
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            feeds.append((f"Yahoo Finance ({ticker})", url))
    return feeds


def build_google_news_feeds(active_targets):
    """Construct dynamic Google News RSS URLs from active target locks.
    Groups by target_type and chunks to stay within safe URL lengths.
    Filters out non-equity identifiers (CUSIPs, numeric codes) from Ticker queries.
    Returns list of (source_name, feed_url) tuples.
    """
    MAX_TERMS_PER_QUERY = 5

    by_type = {}
    for t in active_targets:
        value = t['target_value']
        # Skip non-equity ticker identifiers in Google News queries — they generate noise
        if t['target_type'] == 'Ticker' and not is_equity_ticker(value):
            continue
        by_type.setdefault(t['target_type'], []).append(value)

    feeds = []
    for target_type, values in by_type.items():
        for i in range(0, len(values), MAX_TERMS_PER_QUERY):
            chunk = values[i:i + MAX_TERMS_PER_QUERY]
            terms = [f'"{v}"' if ' ' in v else v for v in chunk]
            query = ' OR '.join(terms)
            url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            chunk_num = i // MAX_TERMS_PER_QUERY + 1
            label = f"Google News ({target_type})" if len(values) <= MAX_TERMS_PER_QUERY else f"Google News ({target_type} {chunk_num})"
            feeds.append((label, url))

    return feeds


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

# Event types that are always stored regardless of signal or fact count.
# These are material events the user explicitly wants — never discard them.
MATERIAL_EVENT_TYPES = {
    'earnings report', 'earnings call',
    'analyst upgrade', 'analyst downgrade', 'price target change',
    'executive change', 'merger & acquisition',
    'product launch', 'regulatory action', 'material event',
}

# Minimum thresholds for non-material articles to be worth storing.
# An article fails if ALL conditions in any single rule are true.
QUALITY_RULES = [
    # Rule 1: Zero extracted facts AND negative signal — pure opinion/noise
    {"min_facts": 0, "max_facts": 0, "max_signal": -1,  "label": "no-facts + negative signal"},
    # Rule 2: One fact AND strongly negative signal — thin meta-articles
    {"min_facts": 1, "max_facts": 1, "max_signal": -5,  "label": "thin-facts + poor signal"},
    # Rule 3: Hard floor — deeply negative signal regardless of facts
    {"min_facts": 0, "max_facts": 999, "max_signal": -25, "label": "signal floor breach"},
]


def passes_quality_gate(analysis):
    """Return (passes: bool, reason: str).
    Material events (earnings, upgrades, executive changes, etc.) always pass.
    Everything else is checked against QUALITY_RULES.
    """
    event_type = analysis.get('event_type', '').lower().strip()

    # Always store material events — never discard them on signal grounds
    if event_type in MATERIAL_EVENT_TYPES:
        return True, f"material event override ({event_type})"

    facts  = len(analysis.get('current_facts', []))
    signal = analysis.get('impact_score', 0) - analysis.get('hype_score', 0)

    for rule in QUALITY_RULES:
        if rule['min_facts'] <= facts <= rule['max_facts'] and signal <= rule['max_signal']:
            return False, rule['label']

    return True, "ok"


def log_source_quality_reject(cursor, source_name):
    cursor.execute('''
        INSERT INTO source_performance (source_name, quality_rejected_articles, last_updated)
        VALUES (?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(source_name) DO UPDATE SET
            quality_rejected_articles = quality_rejected_articles + 1,
            last_updated = CURRENT_TIMESTAMP
    ''', (source_name,))


# ---------------------------------------------------------------------------
# Telemetry loggers
# ---------------------------------------------------------------------------

def log_ai_usage(cursor, start_time, response, model_name):
    latency = int((time.time() - start_time) * 1000)
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        p_tokens = response.usage_metadata.prompt_token_count
        c_tokens = response.usage_metadata.candidates_token_count
        t_tokens = response.usage_metadata.total_token_count
    else:
        p_tokens = c_tokens = t_tokens = 0
    # Gemini 2.5 Flash pricing: $0.075/1M input, $0.30/1M output
    est_cost = (p_tokens * 0.000000075) + (c_tokens * 0.00000030)
    cursor.execute('''
        INSERT INTO ai_usage_logs
            (model_id, request_type, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, latency_ms, status_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (model_name, 'de-hype-extraction', p_tokens, c_tokens, t_tokens, est_cost, latency, 200))


def log_source_deflect(cursor, source_name):
    cursor.execute('''
        INSERT INTO source_performance (source_name, deflected_articles, last_updated)
        VALUES (?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(source_name) DO UPDATE SET
            deflected_articles = deflected_articles + 1,
            last_updated = CURRENT_TIMESTAMP
    ''', (source_name,))


def log_source_chop(cursor, source_name):
    cursor.execute('''
        INSERT INTO source_performance (source_name, redundant_articles_chopped, last_updated)
        VALUES (?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(source_name) DO UPDATE SET
            redundant_articles_chopped = redundant_articles_chopped + 1,
            last_updated = CURRENT_TIMESTAMP
    ''', (source_name,))


def log_source_ingest(cursor, source_name):
    cursor.execute('''
        INSERT INTO source_performance (source_name, total_articles_ingested, last_updated)
        VALUES (?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(source_name) DO UPDATE SET
            total_articles_ingested = total_articles_ingested + 1,
            last_updated = CURRENT_TIMESTAMP
    ''', (source_name,))


# ---------------------------------------------------------------------------
# AI De-Hype Engine
# ---------------------------------------------------------------------------

def de_hype_article(client, title, summary, cursor, active_targets=None):
    """Call Gemini to extract structured intelligence from a pre-filtered article.
    Injects active targets as context to bias impact scoring toward portfolio relevance.
    """
    target_context = ""
    if active_targets:
        target_values = [t['target_value'] for t in active_targets]
        target_context = (
            f"\nThe user monitors these portfolio positions and subjects: {', '.join(target_values)}. "
            f"Factor relevance to these specifically when scoring impact_score — "
            f"direct relevance to a monitored position should raise the score.\n"
        )

    prompt = f"""Analyze this financial news article and extract structured intelligence.
Title: {title}
Content: {summary}
{target_context}
Instructions:
1. CURRENT FACTS: Extract concrete, verifiable facts happening right now (specific numbers, decisions, actions taken). Be thorough — earnings figures, price targets, analyst ratings, executive changes, and regulatory decisions are all facts.
2. FUTURE OPINIONS: Separate predictions, analyst forecasts, and speculative commentary.
3. ENTITIES: Extract company names, ticker symbols, executives, indices, and institutions.
4. MACRO THEMES: Identify broad themes (e.g., Cryptocurrency, Interest Rates, Oil & Gas, Earnings Season, AI).
5. EVENT TYPE: Classify precisely using the provided categories. Earnings reports, analyst upgrades/downgrades, and price target changes must be classified specifically — do not fall back to 'General News' if a more specific category applies.
6. IMPACT SCORE: Rate 0-100 based on direct, measurable market consequence. Earnings reports, analyst rating changes, and executive departures for portfolio companies score higher.
7. HYPE SCORE: Rate 0-100 based on emotional language and sensationalism. Factual analyst notes score low. Breathless headlines score high.
"""
    start_time = time.time()
    model_name = 'gemini-2.5-flash'
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ArticleAnalysis,
                temperature=0.1
            ),
        )
        log_ai_usage(cursor, start_time, response, model_name)

        raw_json = response.text.strip()
        if raw_json.startswith('```json'):
            raw_json = raw_json[7:]
        if raw_json.endswith('```'):
            raw_json = raw_json[:-3]
        return json.loads(raw_json.strip())

    except Exception as e:
        logging.error(f"AI Engine failure for '{title}': {e}")
        return {
            "dehyped_summary": "AI Processing Failed due to structural anomaly.",
            "current_facts": [],
            "future_opinions": [],
            "entities": [],
            "macro_themes": [],
            "event_type": "Error",
            "hype_score": 0,
            "impact_score": 0,
        }


# ---------------------------------------------------------------------------
# Article scraper
# ---------------------------------------------------------------------------

def fetch_article_text(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            logging.warning(f"Shields up at {url} (HTTP {response.status_code}).")
            return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        markdown_text = markdownify.markdownify(str(soup), heading_style="ATX", strip=['a', 'img']).strip()
        if markdown_text:
            return markdown_text[:4000] + "\n...[TRUNCATED]"
        return "No readable content extracted."
    except Exception as e:
        logging.warning(f"Scraper failed for {url}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Main ingestion cycle
# ---------------------------------------------------------------------------

def main():
    if not API_KEY:
        logging.error("CRITICAL: GEMINI_API_KEY not found in .env. Halting.")
        return

    logging.info("Initializing DB Matrix & Telemetry Vault...")
    conn = init_db()
    cursor = conn.cursor()

    # --- Load targeting data FIRST — it drives everything ---
    active_keywords = load_active_keywords(cursor)
    active_targets  = load_active_targets(cursor)
    keywords_map    = load_target_keywords_map(cursor)

    if not active_keywords:
        logging.warning("=" * 60)
        logging.warning("⚠️  NO TRACKING TARGETS CONFIGURED — nothing to fetch.")
        logging.warning("   Open http://localhost:8001 in your browser.")
        logging.warning("   Click 'Edit' in the Tracking panel.")
        logging.warning("   Add a ticker (e.g. AAPL) or topic (e.g. Gold).")
        logging.warning("   Then re-run: docker exec intelligence python ingestor.py")
        logging.warning("=" * 60)
        conn.close()
        return

    logging.info(f"🎯 {len(active_targets)} active targets | {len(active_keywords)} deflector keywords loaded.")

    # --- Vector containment field ---
    logging.info("Initializing Vector Containment Field...")
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = chroma_client.get_or_create_collection(
        name="news_vectors",
        metadata={"hnsw:space": "cosine"}
    )

    client = genai.Client(api_key=API_KEY)

    # --- Build full source list: static registry + dynamic feeds ---
    cursor.execute("SELECT source_name, feed_url FROM source_registry WHERE is_active = 1")
    all_sources = [(row['source_name'], row['feed_url']) for row in cursor.fetchall()]

    ticker_feeds  = build_ticker_rss_feeds(active_targets)   # per-ticker Yahoo Finance
    google_feeds  = build_google_news_feeds(active_targets)   # topic/macro Google News
    all_sources.extend(ticker_feeds)
    all_sources.extend(google_feeds)

    if not all_sources:
        logging.warning("No active sources. Aborting.")
        conn.close()
        return

    logging.info(f"📡 {len(all_sources)} sources active ({len(ticker_feeds)} per-ticker, {len(google_feeds)} Google News).")

    # --- Process each source ---
    for source_name, feed_url in all_sources:
        logging.info(f"Scanning: {source_name} ({feed_url[:60]}...)")
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:10]:
                title        = entry.get('title', 'Unknown Title')
                link         = entry.get('link', '')
                published_at = entry.get('published', datetime.now().isoformat())

                # Extract best available raw text from the feed entry
                raw_content  = ""
                if 'content' in entry and len(entry.content) > 0:
                    raw_content = entry.content[0].value
                raw_summary = entry.get('summary', entry.get('description', ''))
                text_to_scrub = raw_content if len(raw_content) > len(raw_summary) else raw_summary

                if text_to_scrub:
                    summary_soup = BeautifulSoup(text_to_scrub, 'html.parser')
                    summary = summary_soup.get_text(separator=' ', strip=True)
                else:
                    summary = ""

                # Fallback: scrape the article if RSS body is too short
                if len(summary) < 50 and link:
                    scraped = fetch_article_text(link)
                    if scraped:
                        summary = scraped

                if not summary or len(summary) < 10:
                    summary = "No summary provided."

                # ==========================================================
                # LEVEL 1: DEFLECTOR — keyword relevance gate (zero-cost)
                # ==========================================================
                if not is_relevant(title, summary, active_keywords):
                    logging.info(f"🛡️  DEFLECTED: {title[:80]}")
                    log_source_deflect(cursor, source_name)
                    conn.commit()
                    continue

                # ==========================================================
                # LEVEL 2: SEMANTIC DEDUPLICATION — ChromaDB chopper
                # ==========================================================
                existing = collection.query(query_texts=[summary], n_results=1)
                if existing['distances'] and existing['distances'][0]:
                    distance = existing['distances'][0][0]
                    if distance < 0.15:
                        logging.info(f"🪓 CHOPPED! Similarity {distance:.2f}. Skipping AI.")
                        log_source_chop(cursor, source_name)
                        conn.commit()
                        continue

                # ==========================================================
                # LEVEL 3: AI DE-HYPE ENGINE — Gemini extraction
                # ==========================================================
                logging.info(f"🧠 Engaging AI Engine: {title[:80]}")
                analysis = de_hype_article(client, title, summary, cursor, active_targets)

                # ==========================================================
                # LEVEL 4: QUALITY GATE — discard thin meta-articles
                # ==========================================================
                passed, reason = passes_quality_gate(analysis)
                if not passed:
                    logging.info(f"🗑️  QUALITY REJECTED ({reason}): {title[:80]}")
                    log_source_quality_reject(cursor, source_name)
                    conn.commit()
                    continue

                entities     = analysis.get('entities', [])
                macro_themes = analysis.get('macro_themes', [])
                matched      = compute_matched_targets(entities, macro_themes, active_targets, keywords_map, title, summary)

                try:
                    cursor.execute('''
                        INSERT INTO articles (
                            title, summary, dehyped_summary, current_facts, future_opinions,
                            entities, macro_themes, event_type, hype_score, impact_score,
                            source, link, published_at, matched_targets
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        title,
                        summary,
                        analysis.get('dehyped_summary', ''),
                        json.dumps(analysis.get('current_facts', [])),
                        json.dumps(analysis.get('future_opinions', [])),
                        json.dumps(entities),
                        json.dumps(macro_themes),
                        analysis.get('event_type', 'General News'),
                        analysis.get('hype_score', 0),
                        analysis.get('impact_score', 0),
                        source_name,
                        link,
                        published_at,
                        json.dumps(matched),
                    ))
                    log_source_ingest(cursor, source_name)
                    conn.commit()

                    doc_id = link if link else title
                    collection.add(
                        documents=[summary],
                        metadatas=[{"title": title, "source": source_name}],
                        ids=[doc_id]
                    )
                    logging.info(f"✅ Stored. Matched targets: {matched}")

                except sqlite3.IntegrityError:
                    logging.warning(f"⚠️  Duplicate title, skipping.")
                except Exception as e:
                    logging.error(f"❌ DB Write Error: {e}")

        except Exception as source_error:
            logging.error(f"Source failure [{source_name}]: {source_error}")
            continue

    conn.close()
    logging.info("Ingestion cycle complete.")


if __name__ == "__main__":
    main()
