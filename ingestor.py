import feedparser
import sqlite3
import json
import os
import time
import logging
import requests
import chromadb
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

# DB & Vector Coordinates
DB_PATH = Path(__file__).parent / "intelligence.db"
CHROMA_PATH = Path(__file__).parent / "chroma_db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Matrix core data schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            summary TEXT,
            dehyped_summary TEXT,
            current_facts TEXT,
            future_opinions TEXT,
            hype_score INTEGER,
            impact_score INTEGER,
            source TEXT,
            link TEXT,
            published_at TEXT
        )
    ''')
    
    # Operational Telemetry schemas
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS source_performance (
            source_name TEXT PRIMARY KEY,
            total_articles_ingested INTEGER DEFAULT 0,
            redundant_articles_chopped INTEGER DEFAULT 0,
            average_hype_score REAL DEFAULT 0.0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Schema Evolution Safety check
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN current_facts TEXT")
        cursor.execute("ALTER TABLE articles ADD COLUMN future_opinions TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return conn

def log_ai_usage(cursor, start_time, response, model_name):
    latency = int((time.time() - start_time) * 1000)
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        p_tokens = response.usage_metadata.prompt_token_count
        c_tokens = response.usage_metadata.candidates_token_count
        t_tokens = response.usage_metadata.total_token_count
    else:
        p_tokens = c_tokens = t_tokens = 0
        
    # Gemini 2.5 Flash Approx Pricing: $0.075/1M Input, $0.30/1M Output
    est_cost = (p_tokens * 0.000000075) + (c_tokens * 0.00000030)
    
    cursor.execute('''
        INSERT INTO ai_usage_logs (model_id, request_type, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, latency_ms, status_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (model_name, 'de-hype-extraction', p_tokens, c_tokens, t_tokens, est_cost, latency, 200))

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

def de_hype_article(client, title, summary, cursor):
    prompt = f"""
    Analyze this news article.
    Title: {title}
    Content: {summary}
    
    Categorize the temporal intelligence: separate 'Current Facts' (things happening right now) from 'Future Opinions' (predictions, analyst guesses, hype).
    
    Provide a JSON response strictly matching this schema:
    {{
        "dehyped_summary": "A purely objective, factual 1-2 sentence summary without emotional adjectives.",
        "current_facts": ["fact 1", "fact 2"],
        "future_opinions": ["prediction 1", "opinion 1"],
        "hype_score": [0-100 integer evaluating sensationalism],
        "impact_score": [0-100 integer evaluating actual market impact]
    }}
    """
    start_time = time.time()
    model_name = 'gemini-2.5-flash'
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        log_ai_usage(cursor, start_time, response, model_name)
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"AI Engine failure for '{title}': {e}")
        return {
            "dehyped_summary": "AI Processing Failed.",
            "current_facts": [],
            "future_opinions": [],
            "hype_score": 0,
            "impact_score": 0
        }

def fetch_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs if len(p.get_text()) > 20])
        if text:
            return text[:2000] + "..."
        return "No readable content extracted."
    except Exception as e:
        logging.warning(f"Scraper array failed for {url}: {e}")
        return "Failed to fetch article content."

def main():
    if not API_KEY:
        logging.error("CRITICAL: GEMINI_API_KEY not found in .env. Halting ignition sequence.")
        return

    logging.info("Initializing DB Matrix & Telemetry Vault...")
    conn = init_db()
    cursor = conn.cursor()

    logging.info("Initializing Vector Containment Field...")
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = chroma_client.get_or_create_collection(
        name="news_vectors",
        metadata={"hnsw:space": "cosine"}
    )

    client = genai.Client(api_key=API_KEY)

    source_name = 'Yahoo Finance'
    feed_url = 'https://finance.yahoo.com/news/rssindex'
    logging.info(f"Scanning comms frequencies: {feed_url}")
    feed = feedparser.parse(feed_url)

    for entry in feed.entries[:15]:
        title = entry.get('title', 'Unknown Title')
        link = entry.get('link', '')
        published_at = entry.get('published', datetime.now().isoformat())
        
        summary = entry.get('summary', entry.get('description', ''))
        if len(summary) < 50 and link:
            summary = fetch_article_text(link)
            
        if not summary or len(summary) < 10:
            summary = "No summary provided and scraping failed."

        # 🪓 REDUNDANT CHOPPING
        existing = collection.query(query_texts=[summary], n_results=1)
        if existing['distances'] and existing['distances'][0]:
            distance = existing['distances'][0][0]
            if distance < 0.15: # 85% similarity threshold
                logging.info(f"🪓 CHOPPED! Vector overlap {distance:.2f}. Bypassing AI API.")
                log_source_chop(cursor, source_name)
                conn.commit()
                continue

        logging.info(f"🧠 Novel intelligence detected. Engaging AI Engine...")
        analysis = de_hype_article(client, title, summary, cursor)

        try:
            cursor.execute('''
                INSERT INTO articles (
                    title, summary, dehyped_summary, current_facts, future_opinions, 
                    hype_score, impact_score, source, link, published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                summary,
                analysis.get('dehyped_summary', ''),
                json.dumps(analysis.get('current_facts', [])),
                json.dumps(analysis.get('future_opinions', [])),
                analysis.get('hype_score', 0),
                analysis.get('impact_score', 0),
                source_name,
                link,
                published_at
            ))
            log_source_ingest(cursor, source_name)
            conn.commit()
            
            doc_id = link if link else title
            collection.add(
                documents=[summary],
                metadatas=[{"title": title, "source": source_name}],
                ids=[doc_id]
            )
            logging.info(f"✅ Successfully processed & embedded.")
        except sqlite3.IntegrityError:
            logging.warning(f"⚠️ Duplicate title detected in SQLite, skipping.")
        except Exception as e:
            logging.error(f"❌ DB Write Error: {e}")

    conn.close()
    logging.info("Ingestion cycle complete.")

if __name__ == "__main__":
    main()
