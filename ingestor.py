import feedparser
import sqlite3
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load Environment Life Support
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# DB Coordinates
DB_PATH = Path(__file__).parent / "intelligence.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Scotty's Override: Atomize old schema to prevent column mismatch
    cursor.execute("DROP TABLE IF EXISTS articles")
    
    cursor.execute('''
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            summary TEXT,
            dehyped_summary TEXT,
            hype_score INTEGER,
            impact_score INTEGER,
            source TEXT,
            published_at TEXT
        )
    ''')
    conn.commit()
    return conn

def de_hype_article(client, title, summary):
    prompt = f"""
    Analyze this news article.
    Title: {title}
    Summary: {summary}
    
    Provide a JSON response strictly matching this schema:
    {{
        "dehyped_summary": "A purely objective, factual 1-2 sentence summary without emotional adjectives.",
        "hype_score": [0-100 integer evaluating sensationalism],
        "impact_score": [0-100 integer evaluating actual market impact]
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"AI Engine failure for '{title}': {e}")
        return {
            "dehyped_summary": "AI Processing Failed.",
            "hype_score": 0,
            "impact_score": 0
        }

def main():
    if not API_KEY:
        logging.error("CRITICAL: GEMINI_API_KEY not found in .env. Halting ignition sequence.")
        return

    logging.info("Initializing DB Matrix (Purging old schema)...")
    conn = init_db()
    cursor = conn.cursor()

    logging.info("Warming up Gemini AI Core...")
    client = genai.Client(api_key=API_KEY)

    feed_url = 'https://finance.yahoo.com/news/rssindex'
    logging.info(f"Scanning comms frequencies: {feed_url}")
    feed = feedparser.parse(feed_url)

    for entry in feed.entries[:10]:  # Tracer Bullet limit
        title = entry.title
        summary = getattr(entry, 'summary', 'No summary provided.')
        published_at = getattr(entry, 'published', datetime.now().isoformat())

        logging.info(f"🧠 Engaging De-Hype Engine for: {title[:40]}...")
        analysis = de_hype_article(client, title, summary)

        try:
            cursor.execute('''
                INSERT INTO articles (title, summary, dehyped_summary, hype_score, impact_score, source, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                summary,
                analysis.get('dehyped_summary', ''),
                analysis.get('hype_score', 0),
                analysis.get('impact_score', 0),
                'Yahoo Finance',
                published_at
            ))
            conn.commit()
            logging.info(f"✅ Successfully stored: {title[:40]}...")
        except sqlite3.IntegrityError:
            logging.warning(f"⚠️ Duplicate detected, skipping: {title[:40]}...")
        except Exception as e:
            logging.error(f"❌ DB Write Error on '{title[:40]}': {e}")

    conn.close()
    logging.info("Ingestion cycle complete. DB connections severed cleanly.")

if __name__ == "__main__":
    main()
