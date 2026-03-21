import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Intelligence Telemetry API", description="Provides de-hyped briefing data.")

# Absolute path resolution
DB_PATH = Path(__file__).parent / "intelligence.db"

def get_db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Matrix offline: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enables JSON serialization by dictionary conversion
    return conn

@app.get("/health")
def health_check():
    """Diagnostic telemetry for the structural integrity of the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            table_exists = cursor.fetchone() is not None
        return {"status": "online", "matrix_path": str(DB_PATH.name), "articles_table_ready": table_exists}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "offline", "error": str(e)})

@app.get("/api/briefing/latest")
def get_latest_briefing(limit: int = 10):
    """Returns the latest processed intelligence briefings."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify schema exists before querying to prevent fatal 500s
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            if not cursor.fetchone():
                return JSONResponse(status_code=404, content={"message": "Intelligence matrix is currently empty."})

            cursor.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()

            # dict(row) cleanly maps the sqlite3.Row to a JSON-compatible dictionary
            return {"briefings": [dict(row) for row in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Telemetry Error: {str(e)}")
