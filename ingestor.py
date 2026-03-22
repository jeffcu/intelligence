import feedparser
import sqlite3
import json
import os
import logging
import requests
from bs4 import BeautifulSoup
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
    
    # Scotty's Override: Recycling the containment field to upgrade schema with 'link'
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
            link TEXT,
            published_at TEXT
        )
    ''')
    conn.commit()
    return conn

def de_hype_article(client, title, summary):
    prompt = f"""
    Analyze this news article.
    Title: {title}
    Content: {summary}
    
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

def fetch_article_text(url):
    """Tractor beam to pull the raw article text if RSS fails us."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs if len(p.get_text()) > 20])
        if text:
            return text[:2000] + "..." # Truncate to save AI tokens
        return "No readable content extracted."
    except Exception as e:
        logging.warning(f"Scraper array failed for {url}: {e}")
        return "Failed to fetch article content."

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
        title = entry.get('title', 'Unknown Title')
        link = entry.get('link', '')
        published_at = entry.get('published', datetime.now().isoformat())
        
        # Attempt to get summary from feed, otherwise scrape the hull!
        summary = entry.get('summary', entry.get('description', ''))
        if len(summary) < 50 and link:
            logging.info(f"Summary too weak. Engaging tractor beam to pull article: {link}")
            summary = fetch_article_text(link)
            
        if not summary or len(summary) < 10:
            summary = "No summary provided and scraping failed."

        logging.info(f"🧠 Engaging De-Hype Engine for: {title[:40]}...")
        analysis = de_hype_article(client, title, summary)

        try:
            cursor.execute('''
                INSERT INTO articles (title, summary, dehyped_summary, hype_score, impact_score, source, link, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                summary,
                analysis.get('dehyped_summary', ''),
                analysis.get('hype_score', 0),
                analysis.get('impact_score', 0),
                'Yahoo Finance',
                link,
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
