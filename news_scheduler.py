"""
News Ingestion Scheduler
Runs the ingestor at 7:00 AM, 12:00 PM, and 3:00 PM local time, every weekday.
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
PYTHON    = sys.executable

# Scheduled run times: (hour, minute) in local system time
SCHEDULE  = [(7, 0), (12, 0), (15, 0)]


def seconds_until_next_run() -> tuple[float, datetime]:
    """Return (seconds_to_wait, next_run_datetime) for the next scheduled slot."""
    now = datetime.now()
    candidates = []

    for hour, minute in SCHEDULE:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        # Skip Saturday (5) and Sunday (6)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        candidates.append(target)

    next_run = min(candidates)
    return (next_run - now).total_seconds(), next_run


def run_ingestor():
    logging.info("=" * 60)
    logging.info("Triggering news ingestion cycle...")
    try:
        result = subprocess.run(
            [PYTHON, str(INGESTOR)],
            cwd=str(INGESTOR.parent),
            capture_output=False,   # let ingestor logs flow to this terminal
            text=True,
        )
        if result.returncode == 0:
            logging.info("Ingestion cycle completed successfully.")
        else:
            logging.error(f"Ingestor exited with code {result.returncode}.")
    except Exception as e:
        logging.error(f"Failed to launch ingestor: {e}")
    logging.info("=" * 60)


def main():
    logging.info("News Scheduler started.")
    logging.info(f"Schedule: {[f'{h:02d}:{m:02d}' for h, m in SCHEDULE]} local time (weekdays only)")
    logging.info(f"Ingestor: {INGESTOR}")

    while True:
        wait_secs, next_run = seconds_until_next_run()
        logging.info(f"Next ingestion: {next_run.strftime('%A %Y-%m-%d %H:%M')} (in {timedelta(seconds=int(wait_secs))})")
        time.sleep(wait_secs)
        run_ingestor()


if __name__ == "__main__":
    main()
