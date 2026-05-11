"""
News Ingestion + Briefing Scheduler
Runs the ingestor at 7:00 AM, 12:00 PM, and 3:00 PM — every day.
The summarizer runs immediately after each ingest completes.

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

# Ingest times — summarizer runs immediately after each ingest completes.
SCHEDULE = [
    (7,  0),
    (12, 0),
    (15, 0),
]

# Trigger a catch-up ingest on startup if data is older than this many hours.
STALE_INGEST_HOURS = 5


def seconds_until_next_run() -> tuple[float, datetime]:
    """Return (seconds_to_wait, next_run_datetime) for the next scheduled ingest."""
    now = datetime.now()
    candidates = []
    for hour, minute in SCHEDULE:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        candidates.append(target)
    next_run = min(candidates)
    return (next_run - now).total_seconds(), next_run


def last_ingest_time() -> datetime | None:
    """Return the timestamp of the most recent ingest, or None if no history."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM ai_usage_logs")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            ts = datetime.fromisoformat(row[0])
            # Defensive: if the stored timestamp appears future-dated it was likely
            # written as UTC (old CURRENT_TIMESTAMP default). Shift by 7h (PDT).
            if ts > datetime.now() + timedelta(minutes=5):
                ts -= timedelta(hours=7)
            return ts
    except Exception:
        pass
    return None


def run_ingest_then_summarize():
    logging.info("=" * 60)
    logging.info("Step 1/2 — Ingesting news...")
    try:
        result = subprocess.run(
            [PYTHON, str(INGESTOR)],
            cwd=str(INGESTOR.parent),
            capture_output=False,
            text=True,
        )
        if result.returncode != 0:
            logging.error(f"Ingestor exited with code {result.returncode} — skipping summarizer.")
            logging.info("=" * 60)
            return
        logging.info("Ingestion complete.")
    except Exception as e:
        logging.error(f"Failed to launch ingestor: {e} — skipping summarizer.")
        logging.info("=" * 60)
        return

    logging.info("Step 2/2 — Summarizing briefings...")
    try:
        result = subprocess.run(
            [PYTHON, str(SUMMARIZER)],
            cwd=str(SUMMARIZER.parent),
            capture_output=False,
            text=True,
        )
        if result.returncode == 0:
            logging.info("Summarization complete.")
        else:
            logging.error(f"Summarizer exited with code {result.returncode}.")
    except Exception as e:
        logging.error(f"Failed to launch summarizer: {e}")
    logging.info("=" * 60)


def due_slot(last_run: datetime | None) -> datetime | None:
    """
    Return the most recent scheduled slot that has passed but hasn't been run yet.
    Handles the case where the process wakes up right at the scheduled time —
    the slot is already "in the past" by the time we check.
    """
    now = datetime.now()
    best: datetime | None = None
    for hour, minute in SCHEDULE:
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot > now:
            continue  # future — not yet due
        if last_run is not None and slot <= last_run:
            continue  # already ran this slot
        if best is None or slot > best:
            best = slot
    return best


def main():
    schedule_display = [f'{h:02d}:{m:02d}' for h, m in SCHEDULE]
    logging.info("News Scheduler started.")
    logging.info(f"Schedule: {schedule_display} local time — ingest + summarize each run (7 days a week)")

    # On startup, check if data is stale and catch up if so.
    last_run: datetime | None = None
    last = last_ingest_time()
    if last is None:
        logging.info("No ingest history found — running catch-up now.")
        run_ingest_then_summarize()
        last_run = datetime.now()
    else:
        hours_since = (datetime.now() - last).total_seconds() / 3600
        if hours_since > STALE_INGEST_HOURS:
            logging.info(f"Data is {hours_since:.1f}h old (threshold {STALE_INGEST_HOURS}h) — running catch-up.")
            run_ingest_then_summarize()
            last_run = datetime.now()
        else:
            logging.info(f"Data is fresh ({hours_since:.1f}h old) — no catch-up needed.")
            last_run = last  # treat DB timestamp as last run so we don't re-run a fresh slot

    last_logged_next_run = None
    while True:
        # Check if a scheduled slot has passed since the last run.
        slot = due_slot(last_run)
        if slot is not None:
            last_logged_next_run = None
            logging.info(f"Slot {slot.strftime('%H:%M')} is due — running ingest+summarize.")
            run_ingest_then_summarize()
            last_run = slot
            continue  # re-check immediately in case multiple slots were missed

        # Nothing due — sleep until just after the next slot.
        wait_secs, next_run = seconds_until_next_run()
        if next_run != last_logged_next_run:
            logging.info(
                f"Next run: {next_run.strftime('%A %Y-%m-%d %H:%M')} "
                f"(in {timedelta(seconds=int(wait_secs))})"
            )
            last_logged_next_run = next_run

        # Poll every 60 seconds so system sleep/wake doesn't cause missed runs.
        time.sleep(min(60, wait_secs))


if __name__ == "__main__":
    main()
