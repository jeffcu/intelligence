"""
News Ingestion + Briefing Scheduler
Runs the ingestor at 7:00 AM, 12:00 PM, and 3:00 PM, and the
company briefing summarizer at 8:00 AM, 2:00 PM, and 5:00 PM — every day.

Run once and leave it in the background:  python news_scheduler.py
"""

import sqlite3
import subprocess
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

INGESTOR   = Path(__file__).parent / "ingestor.py"
SUMMARIZER = Path(__file__).parent / "summarizer.py"
DB_PATH    = Path(__file__).parent / "intelligence.db"

# Always use the venv Python so feedparser/chromadb etc. are available,
# regardless of which Python launched the scheduler.
_venv_python = Path(__file__).parent / "venv" / "bin" / "python"
PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable

# Scheduled run times: (hour, minute, task)  — runs every day, no weekend skip
SCHEDULE = [
    (7,  0,  'ingest'),
    (8,  0,  'summarize'),
    (12, 0,  'ingest'),
    (14, 0,  'summarize'),
    (15, 0,  'ingest'),
    (17, 0,  'summarize'),
]

# Trigger a catch-up ingest on startup if data is older than this many hours.
STALE_INGEST_HOURS = 5


def seconds_until_next_run() -> tuple[float, datetime, str]:
    """Return (seconds_to_wait, next_run_datetime, task) for the next scheduled slot."""
    now = datetime.now()
    candidates = []
    for hour, minute, task in SCHEDULE:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        candidates.append((target, task))
    next_run, task = min(candidates, key=lambda x: x[0])
    return (next_run - now).total_seconds(), next_run, task


def last_ingest_time() -> datetime | None:
    """Return the timestamp of the most recent ingest, or None if no history."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM ai_usage_logs")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
    except Exception:
        pass
    return None


def run_ingestor():
    logging.info("=" * 60)
    logging.info("Triggering news ingestion cycle...")
    try:
        result = subprocess.run(
            [PYTHON, str(INGESTOR)],
            cwd=str(INGESTOR.parent),
            capture_output=False,
            text=True,
        )
        if result.returncode == 0:
            logging.info("Ingestion cycle completed successfully.")
        else:
            logging.error(f"Ingestor exited with code {result.returncode}.")
    except Exception as e:
        logging.error(f"Failed to launch ingestor: {e}")
    logging.info("=" * 60)


def run_summarizer():
    logging.info("=" * 60)
    logging.info("Triggering daily company briefing summaries...")
    try:
        result = subprocess.run(
            [PYTHON, str(SUMMARIZER)],
            cwd=str(SUMMARIZER.parent),
            capture_output=False,
            text=True,
        )
        if result.returncode == 0:
            logging.info("Briefing generation completed successfully.")
        else:
            logging.error(f"Summarizer exited with code {result.returncode}.")
    except Exception as e:
        logging.error(f"Failed to launch summarizer: {e}")
    logging.info("=" * 60)


def main():
    schedule_display = [f'{h:02d}:{m:02d}[{t}]' for h, m, t in SCHEDULE]
    logging.info("News Scheduler started.")
    logging.info(f"Schedule: {schedule_display} local time (7 days a week)")

    # Catch-up: if data is stale, run ingest immediately before entering the loop.
    last = last_ingest_time()
    if last is None:
        logging.info("No ingest history found — running catch-up ingest now.")
        run_ingestor()
    else:
        hours_since = (datetime.now() - last).total_seconds() / 3600
        if hours_since > STALE_INGEST_HOURS:
            logging.info(f"Data is {hours_since:.1f}h old (threshold {STALE_INGEST_HOURS}h) — running catch-up ingest.")
            run_ingestor()
        else:
            logging.info(f"Data is fresh ({hours_since:.1f}h old) — no catch-up needed.")

    while True:
        wait_secs, next_run, task = seconds_until_next_run()
        logging.info(
            f"Next run: {next_run.strftime('%A %Y-%m-%d %H:%M')} "
            f"[{task}] (in {timedelta(seconds=int(wait_secs))})"
        )
        time.sleep(wait_secs)

        if task == 'summarize':
            run_summarizer()
        else:
            run_ingestor()


if __name__ == "__main__":
    main()
