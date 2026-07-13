from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import sqlglot

app = FastAPI()

# --- Your connection string ---
DATABASE_URL = "postgresql://chatbot_readonly.occiztgbyxtslbuhtavb:Churchgate@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
# --------------------------------

def get_connection():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)

class SQLRequest(BaseModel):
    query: str

@app.get("/schema")
def get_schema(table_name: str = None):
    """Shows what tables and columns exist. Optionally filter to one table."""
    conn = get_connection()
    cur = conn.cursor()
    if table_name:
        cur.execute("""
            select table_name, column_name, data_type
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            order by ordinal_position;
        """, (table_name,))
    else:
        cur.execute("""
            select table_name, column_name, data_type
            from information_schema.columns
            where table_schema = 'public'
            order by table_name, ordinal_position;
        """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    schema = {}
    for table, column, dtype in rows:
        schema.setdefault(table, []).append(f"{column} ({dtype})")
    return schema

@app.post("/execute-sql")
def execute_sql(req: SQLRequest):
    """Safely runs a SELECT query and returns the results."""
    query = req.query.strip()

    # 1. Make sure it's a SELECT/WITH query only, nothing else
    try:
        parsed = sqlglot.parse(query)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not understand this SQL: {e}")

    if len(parsed) != 1:
        raise HTTPException(status_code=400, detail="Only one query at a time is allowed.")

    statement_type = parsed[0].key.lower()
    if statement_type not in ("select", "with"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")

    # 2. Add a safety limit if there isn't one already
    if "limit" not in query.lower():
        query = query.rstrip(";") + " LIMIT 100;"

    print(f"Running SQL: {query}")   # <-- shows the actual query in your terminal

    # 3. Run it
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SET statement_timeout = 5000;")
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query failed: {e}")

    results = [dict(zip(columns, row)) for row in rows]
    return {"results": results}


import requests

API_URL = "https://cloud.flowiseai.com/api/v1/prediction/55e85b17-582c-42fa-9670-62302a602aab"

def query(payload):
    response = requests.post(API_URL, json=payload)
    return response.json()

output = query({
    "question": "Hey, how are you?",
})