import os
import sqlite3
import json
import sys
import threading
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

SUMMARIZER = Path(__file__).parent / "summarizer.py"


DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "intelligence.db")))


def get_db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Matrix offline: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """Ensure all tables and columns exist. Safe to call at startup even if
    ingestor has not yet run — creates only what is missing."""
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_lock_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(target_lock_id, keyword)
        )
    ''')

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

    safe_alters = [
        "ALTER TABLE articles ADD COLUMN matched_targets TEXT",
        "ALTER TABLE source_performance ADD COLUMN deflected_articles INTEGER DEFAULT 0",
        'ALTER TABLE company_summaries ADD COLUMN target_type TEXT DEFAULT "Ticker"',
        'ALTER TABLE source_registry ADD COLUMN country TEXT DEFAULT "US"',
    ]
    for stmt in safe_alters:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(
    title="Intelligence Telemetry API",
    description="Provides de-hyped briefing data and operational telemetry.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SourceCreate(BaseModel):
    source_name: str
    feed_url: str

class TargetCreate(BaseModel):
    target_type: str
    target_value: str

class TargetSyncRequest(BaseModel):
    tickers: list[str]

class KeywordCreate(BaseModel):
    keyword: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health-check")
def root_index():
    return {"status": "online", "message": "Intelligence API Core is humming."}

@app.get("/health")
def health_check():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            table_exists = cursor.fetchone() is not None
        return {"status": "online", "matrix_path": str(DB_PATH.name), "articles_table_ready": table_exists}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "offline", "error": str(e)})


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

@app.get("/api/telemetry/stats")
def get_telemetry_stats():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM articles")
            total_articles = cursor.fetchone()['count']

            cursor.execute("SELECT SUM(redundant_articles_chopped) as chopped, SUM(COALESCE(deflected_articles, 0)) as deflected FROM source_performance")
            row = cursor.fetchone()
            total_chopped   = row['chopped']   or 0
            total_deflected = row['deflected'] or 0

            cursor.execute('''
                SELECT
                    COUNT(*) as total_calls,
                    SUM(total_tokens) as total_tokens,
                    SUM(estimated_cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency
                FROM ai_usage_logs
            ''')
            ai_stats = cursor.fetchone()

            return {
                "total_stored":    total_articles,
                "total_chopped":   total_chopped,
                "total_deflected": total_deflected,
                "ai_calls":        ai_stats['total_calls']  or 0,
                "total_tokens":    ai_stats['total_tokens'] or 0,
                "total_cost_usd":  round(ai_stats['total_cost']    or 0, 6),
                "avg_latency_ms":  round(ai_stats['avg_latency']   or 0, 2),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telemetry Error: {str(e)}")


# ---------------------------------------------------------------------------
# Target Locks
# ---------------------------------------------------------------------------

@app.get("/api/targets")
def get_targets():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tl.id, tl.target_type, tl.target_value, tl.added_at,
                       COUNT(tk.id) as keyword_count
                FROM target_locks tl
                LEFT JOIN target_keywords tk ON tk.target_lock_id = tl.id
                GROUP BY tl.id
                ORDER BY tl.target_type ASC, tl.target_value ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Target Matrix Error: {str(e)}")


@app.post("/api/targets")
def add_target(target: TargetCreate):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO target_locks (target_type, target_value) VALUES (?, ?)
            ''', (target.target_type, target.target_value))
            new_id = cursor.lastrowid
            # Seed the target value itself as a keyword so the deflector works immediately
            cursor.execute('''
                INSERT OR IGNORE INTO target_keywords (target_lock_id, keyword)
                VALUES (?, ?)
            ''', (new_id, target.target_value.lower()))
            conn.commit()
            return {"status": "success", "id": new_id, "message": f"Target lock acquired on {target.target_value}."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Sensor is already locked onto this target.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/targets/{target_id}")
def delete_target(target_id: int):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM target_keywords WHERE target_lock_id = ?", (target_id,))
            cursor.execute("DELETE FROM target_locks WHERE id = ?", (target_id,))
            conn.commit()
            return {"status": "success", "message": "Target lock released."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/targets/sync")
def sync_targets(request: TargetSyncRequest):
    """Bulk upsert ticker symbols from the Trust portfolio.
    Only adds new tickers — never removes manually-added targets.
    Automatically seeds the ticker symbol as a deflector keyword.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            def _is_equity_ticker(v: str) -> bool:
                """Reject CUSIPs, numeric fund codes, and 5-char X-ending mutual funds."""
                if not v or v[0].isdigit() or len(v) >= 8:
                    return False
                if len(v) == 5 and v.upper().endswith('X'):
                    return False
                return True

            new_count = 0
            for ticker in request.tickers:
                ticker = ticker.strip().upper()
                if not ticker or not _is_equity_ticker(ticker):
                    continue

                # Check existence before insert to avoid lastrowid ambiguity
                cursor.execute("SELECT id FROM target_locks WHERE target_value = ?", (ticker,))
                existing = cursor.fetchone()

                if existing:
                    target_id = existing['id']
                else:
                    cursor.execute('''
                        INSERT INTO target_locks (target_type, target_value)
                        VALUES ('Ticker', ?)
                    ''', (ticker,))
                    target_id = cursor.lastrowid
                    new_count += 1

                # Always ensure the ticker symbol keyword exists
                cursor.execute('''
                    INSERT OR IGNORE INTO target_keywords (target_lock_id, keyword)
                    VALUES (?, ?)
                ''', (target_id, ticker.lower()))

            conn.commit()
            return {
                "status":      "success",
                "new_targets": new_count,
                "skipped":     len(request.tickers) - new_count,
                "message":     f"{new_count} new ticker lock(s) acquired.",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Target Keywords
# ---------------------------------------------------------------------------

@app.get("/api/targets/{target_id}/keywords")
def get_target_keywords(target_id: int):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM target_locks WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Target not found.")
            cursor.execute('''
                SELECT id, keyword, added_at FROM target_keywords
                WHERE target_lock_id = ? ORDER BY keyword ASC
            ''', (target_id,))
            return [dict(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/targets/{target_id}/keywords")
def add_target_keyword(target_id: int, body: KeywordCreate):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM target_locks WHERE id = ?", (target_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Target not found.")
            cursor.execute('''
                INSERT INTO target_keywords (target_lock_id, keyword) VALUES (?, ?)
            ''', (target_id, body.keyword.strip().lower()))
            new_id = cursor.lastrowid
            conn.commit()
            return {"status": "success", "id": new_id, "keyword": body.keyword.strip().lower()}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Keyword already exists for this target.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/targets/{target_id}/keywords/{keyword_id}")
def delete_target_keyword(target_id: int, keyword_id: int):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM target_keywords WHERE id = ? AND target_lock_id = ?
            ''', (keyword_id, target_id))
            conn.commit()
            return {"status": "success", "message": "Keyword removed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------

@app.get("/api/briefing/latest")
def get_latest_briefing(limit: int = 50, target: Optional[str] = None):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            if not cursor.fetchone():
                return JSONResponse(status_code=404, content={"message": "Intelligence matrix is currently empty."})

            if target:
                # Filter to articles where matched_targets JSON array contains this value
                cursor.execute('''
                    SELECT * FROM articles
                    WHERE EXISTS (
                        SELECT 1 FROM json_each(COALESCE(matched_targets, '[]'))
                        WHERE value = ?
                    )
                    ORDER BY id DESC LIMIT ?
                ''', (target, limit))
            else:
                cursor.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,))

            rows = cursor.fetchall()
            briefings = []
            for row in rows:
                d = dict(row)
                d['current_facts']   = json.loads(d['current_facts'])   if d.get('current_facts')   else []
                d['future_opinions'] = json.loads(d['future_opinions'])  if d.get('future_opinions') else []
                d['entities']        = json.loads(d['entities'])         if d.get('entities')        else []
                d['matched_targets'] = json.loads(d['matched_targets'])  if d.get('matched_targets') else []
                try:
                    d['macro_themes'] = json.loads(d.get('macro_themes', '[]')) if d.get('macro_themes') else []
                except Exception:
                    d['macro_themes'] = []
                briefings.append(d)

            return {"briefings": briefings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Briefing Error: {str(e)}")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@app.get("/api/sources")
def get_sources():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sr.source_name, sr.feed_url, sr.is_active, sr.added_at, sr.country,
                       COALESCE(sp.total_articles_ingested, 0)       as total_articles_ingested,
                       COALESCE(sp.redundant_articles_chopped, 0)    as redundant_articles_chopped,
                       COALESCE(sp.deflected_articles, 0)            as deflected_articles,
                       COALESCE(sp.average_hype_score, 0.0)          as average_hype_score
                FROM source_registry sr
                LEFT JOIN source_performance sp ON sr.source_name = sp.source_name
                ORDER BY sr.source_name ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Source Matrix Error: {str(e)}")


@app.post("/api/sources")
def add_source(source: SourceCreate):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO source_registry (source_name, feed_url, is_active) VALUES (?, ?, 1)
            ''', (source.source_name, source.feed_url))
            conn.commit()
            return {"status": "success", "message": f"Source {source.source_name} added to matrix."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Source already exists in the matrix.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sources/{source_name}/toggle")
def toggle_source(source_name: str):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE source_registry
                SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
                WHERE source_name = ?
            ''', (source_name,))
            conn.commit()
            return {"status": "success", "message": f"Source {source_name} toggled."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

@app.get("/api/graph")
def get_knowledge_graph():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source, entities, macro_themes, impact_score, title, published_at
                FROM articles ORDER BY id DESC LIMIT 150
            ''')
            rows = cursor.fetchall()

            nodes = {}
            links = []

            for row in rows:
                source = row['source']
                impact = row['impact_score'] or 10
                title  = row['title']
                date   = row['published_at']

                if source not in nodes:
                    nodes[source] = {"id": source, "group": "source", "val": 0}
                nodes[source]["val"] += impact / 10

                entities = json.loads(row['entities'])    if row['entities']    else []
                themes   = json.loads(row['macro_themes']) if row['macro_themes'] else []

                for entity in entities:
                    if entity not in nodes:
                        nodes[entity] = {"id": entity, "group": "entity", "val": 1}
                    nodes[entity]["val"] += 1
                    links.append({"source": source, "target": entity, "impact": impact, "title": title, "date": date})

                for theme in themes:
                    if theme not in nodes:
                        nodes[theme] = {"id": theme, "group": "theme", "val": 2}
                    nodes[theme]["val"] += 1
                    links.append({"source": source, "target": theme, "impact": impact, "title": title, "date": date})

            return {"nodes": list(nodes.values()), "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Matrix Error: {str(e)}")


# ---------------------------------------------------------------------------
# Company Summaries
# ---------------------------------------------------------------------------

@app.get("/api/summaries/latest")
def get_latest_summaries():
    """Return the most recent briefing paragraph per tracked ticker."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_summaries'")
            if not cursor.fetchone():
                return []
            # Most recent row per ticker — MAX(rowid) breaks ties when two runs
            # produce identical generated_at timestamps (parallel summarizer race).
            cursor.execute('''
                SELECT cs.*
                FROM company_summaries cs
                WHERE cs.rowid IN (
                    SELECT MAX(rowid) FROM company_summaries GROUP BY target_value
                )
                ORDER BY cs.target_value ASC
            ''')
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d['key_facts'] = json.loads(d['key_facts']) if d.get('key_facts') else []
                results.append(d)
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summaries Error: {str(e)}")


@app.post("/api/summaries/generate")
def trigger_generate_summaries():
    """Kick off summarizer.py in a background thread. Returns immediately."""
    if not SUMMARIZER.exists():
        raise HTTPException(status_code=503, detail="summarizer.py not found.")

    def _run():
        try:
            subprocess.run(
                [sys.executable, str(SUMMARIZER)],
                cwd=str(SUMMARIZER.parent),
            )
        except Exception as exc:
            import logging
            logging.error(f"Background summarizer failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": "Briefing generation running in the background."}


# ---------------------------------------------------------------------------
# Earnings Calendar
# ---------------------------------------------------------------------------

def _earnings_date_label(epoch_seconds: int) -> str:
    """Convert a Unix timestamp to a human calendar label relative to today."""
    from datetime import date, timedelta
    today = date.today()
    event = date.fromtimestamp(epoch_seconds)
    delta = (event - today).days
    if delta == 0:   return 'Today'
    if delta == 1:   return 'Tomorrow'
    if delta == -1:  return 'Yesterday'
    if -7 < delta < 0:  return f'{abs(delta)}d ago'
    if 1 < delta <= 7:  return event.strftime('%A')       # e.g. "Wednesday"
    if 7 < delta <= 14: return 'Next Week'
    if delta > 14:   return event.strftime('%b %-d')      # e.g. "May 12"
    return event.strftime('%b %-d')


@app.get("/api/earnings-calendar")
def get_earnings_calendar():
    """
    Return upcoming / recent earnings dates for all tracked tickers via yfinance.
    """
    import yfinance as yf
    from datetime import date
    import time

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT target_value FROM target_locks WHERE target_type = 'Ticker'")
            tickers = [row['target_value'] for row in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    today = date.today()
    results = []

    for ticker in tickers:
        try:
            cal = yf.Ticker(ticker).calendar
            if not cal or 'Earnings Date' not in cal:
                continue
            dates = cal['Earnings Date']
            if not dates:
                continue
            event_date = dates[0]
            if hasattr(event_date, 'date'):
                event_date = event_date.date()
            delta = (event_date - today).days
            if delta > 90 or delta < -14:
                continue
            ts = int(time.mktime(event_date.timetuple()))
            results.append({
                'ticker':    ticker,
                'date':      event_date.isoformat(),
                'label':     _earnings_date_label(ts),
                'delta':     delta,
                'confirmed': len(dates) == 1,
                'eps_est':   round(float(cal.get('Earnings Average') or 0), 2),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x['delta'])
    return results


# ---------------------------------------------------------------------------
# IPO Events
# ---------------------------------------------------------------------------

_IPO_TITLE_RE = __import__('re').compile(
    r'\bIPO\b|S-1 filing|files? for IPO|initial public offering|going public|'
    r'IPO pric\w+|IPO sched\w+|IPO date|set to (?:go|list)|begin(?:s)? trading|'
    r'priced? its IPO|direct listing|SPAC merger',
    __import__('re').IGNORECASE
)

@app.get("/api/ipo-events")
def get_ipo_events():
    """
    Return IPO milestone articles (filings, pricings, trading start dates).
    Strictly filters for actual IPO events, not general coverage.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, link, source, published_at, entities, current_facts
                FROM articles
                WHERE (
                    title LIKE '%IPO%'
                    OR title LIKE '%S-1%'
                    OR title LIKE '%going public%'
                    OR title LIKE '%initial public offering%'
                    OR title LIKE '%direct listing%'
                )
                AND published_at >= datetime('now', '-30 days')
                ORDER BY published_at DESC
                LIMIT 40
            ''')
            rows = cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    events = []
    for row in rows:
        d = dict(row)
        title = d.get('title', '')
        if not _IPO_TITLE_RE.search(title):
            continue

        entities = []
        try:
            entities = json.loads(d['entities']) if d.get('entities') else []
        except Exception:
            pass

        facts = []
        try:
            facts = json.loads(d['current_facts']) if d.get('current_facts') else []
        except Exception:
            pass

        # Determine stage from title
        tl = title.lower()
        if 's-1' in tl or 'files for ipo' in tl or 'files to raise' in tl or ('file' in tl and 'ipo' in tl):
            stage = 'Filed S-1'
        elif 'pric' in tl and 'ipo' in tl:
            stage = 'Priced'
        elif 'begin' in tl and 'trading' in tl:
            stage = 'Trading'
        elif any(w in tl for w in ('scheduled', 'plans ipo', 'eyes ipo', 'mulls ipo', 'ipo date', 'set to list', 'set for ipo')):
            stage = 'Scheduled'
        elif 'going public' in tl or 'initial public offering' in tl:
            stage = 'Going Public'
        elif 'ipo' in tl and any(w in tl for w in ('biggest', 'jumps', 'surges', 'raises', 'touting', 'frenzy', 'investor')):
            stage = 'Active'
        elif 'vesting' in tl or 'employee shares' in tl:
            stage = 'Pre-IPO'
        else:
            stage = 'Pipeline'

        events.append({
            'id':           d['id'],
            'title':        title,
            'link':         d.get('link', ''),
            'source':       d.get('source', ''),
            'published_at': d.get('published_at', ''),
            'entities':     entities[:3],
            'stage':        stage,
            'top_fact':     facts[0] if facts else None,
        })

    return events[:10]


# ---------------------------------------------------------------------------
# Static frontend (production / Docker only — skipped in dev)
# ---------------------------------------------------------------------------

_DIST = Path(__file__).parent / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    cwd = Path.cwd().name
    module_path = "api:app" if cwd == "intelligence" else "projects.intelligence.api:app"

    uvicorn.run(
        module_path,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8001)),
        reload=False,
    )
