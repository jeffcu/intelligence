import sqlite3
import textwrap
from pathlib import Path

# Absolute tracking beacon
DB_PATH = Path(__file__).parent / "intelligence.db"

def read_matrix():
    print("\n🔭 Accessing Intelligence Matrix...\n")
    
    if not DB_PATH.exists():
        print(f"❌ Database offline. No matrix detected at {DB_PATH}")
        print("   Run python ingestor.py first.")
        return

    try:
        # Read-only mode to prevent subspace locking
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row  # Crucial for exact column mapping
        cursor = conn.cursor()

        # Verify table integrity
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
        if not cursor.fetchone():
            print("❌ Table 'articles' not found. Ingestor failed to create schema.")
            return

        cursor.execute("SELECT * FROM articles ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()

        if not rows:
            print("📫 Matrix is empty. No signals detected.")
            return

        for row in rows:
            data = dict(row)
            title = data.get('title', 'Unknown Signal')
            hype = data.get('hype_score', 'N/A')
            impact = data.get('impact_score', 'N/A')
            summary = data.get('dehyped_summary', 'No summary available.')
            
            print(f"📰 {title}")
            print(f"   Sensationalism (Hype): {hype}/100 | Impact: {impact}/100")
            wrapped_summary = textwrap.fill(str(summary), width=80, initial_indent="   ", subsequent_indent="   ")
            print(f"{wrapped_summary}")
            print("-" * 60)

    except sqlite3.Error as e:
        print(f"❌ Subspace interference (Database error): {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    read_matrix()
