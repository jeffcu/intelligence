import sqlite3
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Intelligence Telemetry API", description="Provides de-hyped briefing data and operational telemetry.")

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
    return {"status": "online", "message": "Intelligence API Core is humming. Point your browser to port 5173 for the React UI."}

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

@app.get("/api/telemetry/stats")
def get_telemetry_stats():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total Articles Stored
            cursor.execute("SELECT COUNT(*) as count FROM articles")
            total_articles = cursor.fetchone()['count']
            
            # Total Duplicates Chopped
            cursor.execute("SELECT SUM(redundant_articles_chopped) as chopped FROM source_performance")
            row = cursor.fetchone()
            total_chopped = row['chopped'] if row and row['chopped'] else 0
            
            # AI Usage Metrics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(total_tokens) as total_tokens,
                    SUM(estimated_cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency
                FROM ai_usage_logs
            ''')
            ai_stats = cursor.fetchone()
            
            return {
                "total_stored": total_articles,
                "total_chopped": total_chopped,
                "ai_calls": ai_stats['total_calls'] or 0,
                "total_tokens": ai_stats['total_tokens'] or 0,
                "total_cost_usd": round(ai_stats['total_cost'] or 0, 6),
                "avg_latency_ms": round(ai_stats['avg_latency'] or 0, 2)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telemetry Error: {str(e)}")

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
            
            briefings = []
            for row in rows:
                d = dict(row)
                # Decode the temporal JSON strings into arrays for the frontend
                d['current_facts'] = json.loads(d['current_facts']) if d.get('current_facts') else []
                d['future_opinions'] = json.loads(d['future_opinions']) if d.get('future_opinions') else []
                briefings.append(d)
                
            return {"briefings": briefings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Telemetry Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    
    # Scotty's Shielded Ignition Switch
    # Dynamically targets the right module path whether you execute from the root or the module folder
    cwd = Path.cwd().name
    module_path = "api:app" if cwd == "intelligence" else "projects.intelligence.api:app"
    
    uvicorn.run(
        module_path,
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_excludes=[".venv*", "chroma_db*", "*.db", "*.db-journal", "__pycache__*"]
    )
