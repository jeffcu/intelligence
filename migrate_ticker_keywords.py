"""
Migration: seed company name keywords for all Ticker targets.

Steps:
1. Remove duplicate lowercase ticker entries (e.g. "nvda" when "NVDA" exists)
2. Seed ticker symbol + company name keywords for all equity tickers
3. Recompute matched_targets for all existing articles (title-only for tickers)
"""

import sqlite3
import json
import re
import time
import requests
from pathlib import Path

DB_PATH = Path(__file__).parent / "intelligence.db"

# Words in a Yahoo Finance name that indicate a fund/ETF, not an operating company.
# For these we skip the verbose fund name — the ticker symbol keyword is sufficient.
FUND_INDICATORS = {'etf', 'fund', 'trust', 'index', 'bond', 'portfolio',
                   'strategy', 'income', 'growth', 'municipal', 'mlp', 'pimco',
                   'vanguard', 'ishares', 'invesco', 'spdr', 'fidelity', 'schwab'}


def is_equity_ticker(value):
    """True if the value looks like a tradeable equity ticker (1-5 uppercase letters).
    Excludes bond CUSIPs (e.g. 91282CFU0) and numeric fund codes (9999227).
    """
    return bool(re.match(r'^[A-Z]{1,5}$', value))


def fetch_company_name(ticker):
    """Fetch company short name from Yahoo Finance (free, no API key)."""
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}&quotesCount=1&newsCount=0"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            quotes = (data.get("finance", {}).get("result", {}).get("quotes", [])
                      if "finance" in data else data.get("quotes", []))
            for q in quotes:
                if q.get("symbol", "").upper() == ticker.upper():
                    name = q.get("shortname") or q.get("longname") or ""
                    return name.strip()
    except Exception as e:
        print(f"  WARNING: Yahoo lookup failed for {ticker}: {e}")
    return ""


def normalize_name(name):
    """Lowercase, strip corporate suffixes and punctuation for clean keyword matching."""
    name = name.lower().strip()
    # Strip trailing punctuation first
    name = name.rstrip(".,;:")
    # Strip corporate suffixes using endswith so we don't mangle mid-word substrings
    suffixes = [
        " corporation", " incorporated", " inc.", " inc",
        " corp.", " corp", " ltd.", " ltd", " llc", " plc",
        " co.", " co", " class a", " class b", " class c",
        " technologies", " technology", " systems", " group",
        ".com",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    # Final punctuation cleanup
    return name.rstrip(".,;:").strip()


def is_fund_name(name):
    """Return True if the Yahoo Finance name looks like a fund/ETF, not an operating company."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in FUND_INDICATORS)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------------------------------------------------------
    # Step 1: Remove lowercase duplicate tickers (keep uppercase canonical form)
    # -------------------------------------------------------------------------
    print("Step 1: Removing lowercase duplicate ticker targets...")
    cur.execute("SELECT id, target_value FROM target_locks WHERE target_type = 'Ticker' ORDER BY target_value")
    all_tickers = cur.fetchall()

    seen_upper = {}
    for row in all_tickers:
        upper = row["target_value"].upper()
        if row["target_value"] == upper:
            seen_upper[upper] = row["id"]

    removed = 0
    for row in all_tickers:
        upper = row["target_value"].upper()
        if row["target_value"] != upper and upper in seen_upper:
            print(f"  Removing duplicate: '{row['target_value']}' (canonical: '{upper}')")
            cur.execute("DELETE FROM target_keywords WHERE target_lock_id = ?", (row["id"],))
            cur.execute("DELETE FROM target_locks WHERE id = ?", (row["id"],))
            removed += 1

    conn.commit()
    print(f"  Removed {removed} duplicates.\n")

    # -------------------------------------------------------------------------
    # Step 2: Seed keywords for equity Ticker targets only
    # -------------------------------------------------------------------------
    print("Step 2: Seeding ticker symbol + company name keywords...")
    cur.execute("SELECT id, target_value FROM target_locks WHERE target_type = 'Ticker' ORDER BY target_value")
    tickers = cur.fetchall()

    for row in tickers:
        ticker    = row["target_value"].upper()
        target_id = row["id"]

        # Skip CUSIPs, numeric fund codes, etc.
        if not is_equity_ticker(ticker):
            print(f"  {ticker} -> (skipped — not an equity ticker)")
            continue

        # Always seed the ticker symbol itself
        keywords = [ticker.lower()]
        print(f"  {ticker}", end="", flush=True)

        company_name = fetch_company_name(ticker)
        if company_name:
            if is_fund_name(company_name):
                # Fund/ETF — the verbose name is noise; ticker symbol is sufficient
                print(f" -> (ETF/fund name skipped: '{company_name}')")
            else:
                normalized = normalize_name(company_name)
                if normalized and normalized != ticker.lower():
                    keywords.append(normalized)
                    print(f" -> '{normalized}'")
                else:
                    print(f" -> (name normalized to ticker, skipped)")
        else:
            print(" -> (no name found)")

        # Wipe stale/bad keywords for this target before re-seeding
        cur.execute("DELETE FROM target_keywords WHERE target_lock_id = ?", (target_id,))
        for kw in keywords:
            cur.execute(
                "INSERT OR IGNORE INTO target_keywords (target_lock_id, keyword) VALUES (?, ?)",
                (target_id, kw),
            )

        time.sleep(0.15)  # be polite to Yahoo

    conn.commit()
    print()

    # -------------------------------------------------------------------------
    # Step 3: Recompute matched_targets for all existing articles
    # Tickers match title-only; non-ticker targets match full text.
    # -------------------------------------------------------------------------
    print("Step 3: Recomputing matched_targets for all articles...")

    cur.execute('''
        SELECT tl.target_value, tl.target_type, tk.keyword
        FROM target_keywords tk
        JOIN target_locks tl ON tl.id = tk.target_lock_id
    ''')
    keyword_to_targets = {}
    for row in cur.fetchall():
        kw = row["keyword"].lower()
        keyword_to_targets.setdefault(kw, []).append((row["target_value"], row["target_type"]))

    cur.execute("SELECT id, title, summary, entities, macro_themes FROM articles")
    articles = cur.fetchall()

    updated = 0
    for article in articles:
        title    = article["title"] or ""
        summary  = article["summary"] or ""
        entities = json.loads(article["entities"])     if article["entities"]     else []
        themes   = json.loads(article["macro_themes"]) if article["macro_themes"] else []

        title_text = title.lower()
        full_text  = " ".join([title, summary] + entities + themes).lower()

        matched = set()
        for kw, target_entries in keyword_to_targets.items():
            pattern = r"\b" + re.escape(kw) + r"\b"
            for target_value, target_type in target_entries:
                # Ticker: must appear in the title — a body mention is not the subject
                search_text = title_text if target_type == "Ticker" else full_text
                if re.search(pattern, search_text, re.IGNORECASE):
                    matched.add(target_value)

        cur.execute(
            "UPDATE articles SET matched_targets = ? WHERE id = ?",
            (json.dumps(sorted(matched)), article["id"]),
        )
        updated += 1

    conn.commit()
    print(f"  Updated matched_targets on {updated} articles.\n")

    cur.execute("SELECT COUNT(*) as c FROM articles WHERE matched_targets IS NOT NULL AND matched_targets != '[]'")
    matched_count = cur.fetchone()["c"]
    print(f"Done. {matched_count} articles now have matched_targets.")

    conn.close()


if __name__ == "__main__":
    main()
