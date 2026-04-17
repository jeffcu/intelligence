"""
News Ingestion + Briefing Scheduler
Runs the ingestor at 7:00 AM, 12:00 PM, and 3:00 PM, and the
company briefing summarizer at 2:00 PM — every weekday.

Run once and leave it in the background:  python news_scheduler.py
"""

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

INGESTOR  = Path(__file__).parent / "ingestor.py"
SUMMARIZER = Path(__file__).parent / "summarizer.py"
PYTHON    = sys.executable

# Scheduled run times: (hour, minute, task)
# Tasks: 'ingest' | 'summarize'
SCHEDULE = [
    (7,  0,  'ingest'),
    (12, 0,  'ingest'),
    (14, 0,  'summarize'),   # 2 PM — daily company briefing generation
    (15, 0,  'ingest'),
]


def seconds_until_next_run() -> tuple[float, datetime, str]:
    """Return (seconds_to_wait, next_run_datetime, task) for the next scheduled slot."""
    now = datetime.now()
    candidates = []

    for hour, minute, task in SCHEDULE:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        # Skip Saturday (5) and Sunday (6)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        candidates.append((target, task))

    next_run, task = min(candidates, key=lambda x: x[0])
    return (next_run - now).total_seconds(), next_run, task


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
    logging.info(f"Schedule: {schedule_display} local time (weekdays only)")
    logging.info(f"Ingestor:   {INGESTOR}")
    logging.info(f"Summarizer: {SUMMARIZER}")

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
