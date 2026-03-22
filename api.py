import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Intelligence Telemetry API", description="Provides de-hyped briefing data.")

# Scotty's CORS Bypass for the local React tuning console
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Absolute path resolution
DB_PATH = Path(__file__).parent / "intelligence.db"

def get_db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Matrix offline: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def root_index():
    return {"status": "online", "message": "Intelligence API Core is humming. Point your browser to port 5173 for the React UI, or visit /api/briefing/latest for raw telemetry."}

@app.get("/health")
def health_check():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            table_exists = cursor.fetchone() is not None
        return {"status": "online", "matrix_path": str(DB_PATH.name), "articles_table_ready": table_exists}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "offline", "error": str(e)})

@app.get("/api/briefing/latest")
def get_latest_briefing(limit: int = 50):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            if not cursor.fetchone():
                return JSONResponse(status_code=404, content={"message": "Intelligence matrix is currently empty."})

            cursor.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return {"briefings": [dict(row) for row in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Telemetry Error: {str(e)}")
