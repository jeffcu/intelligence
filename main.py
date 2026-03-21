from fastapi import FastAPI
import duckdb

app = FastAPI(title="Intelligence Engine API")
DB_PATH = 'intelligence.duckdb'

@app.get("/api/briefing/latest")
def get_latest_briefing():
    try:
        with duckdb.connect(DB_PATH) as con:
            # Fetch the raw rows directly from the containment field
            result = con.execute("SELECT * FROM articles ORDER BY ingested_at DESC LIMIT 50").fetchall()
            # Extract column headers to map to JSON objects
            cols = [desc[0] for desc in con.description]
            
            data = [dict(zip(cols, row)) for row in result]
            return {"status": "green", "count": len(data), "articles": data}
    except duckdb.Error as e:
        return {"status": "red", "error": str(e)}
