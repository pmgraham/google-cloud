import os
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.cloud import bigquery

app = FastAPI()

project_id = os.environ.get("PROJECT_ID", "pmgraham-dev-workspace")
dataset_id = os.environ.get("DATASET_ID", "vector_matching_pipeline")

if not re.fullmatch(r"[a-zA-Z0-9_\-]+", project_id) or not re.fullmatch(r"[a-zA-Z0-9_\-]+", dataset_id):
    raise ValueError("Invalid project_id or dataset_id format.")

client = bigquery.Client(project=project_id)
default_dataset_ref = f"{project_id}.{dataset_id}"

# SQL Query Cache
QUERY_CACHE = {}

def preload_queries():
    sql_dir = os.path.join(os.path.dirname(__file__), "sql")
    if os.path.exists(sql_dir):
        for filename in os.listdir(sql_dir):
            if filename.endswith(".sql"):
                with open(os.path.join(sql_dir, filename), "r") as f:
                    QUERY_CACHE[filename] = f.read()
    print(f"Preloaded {len(QUERY_CACHE)} SQL queries.")

preload_queries()

class DecisionUpdate(BaseModel):
    undo_review: Optional[bool] = None
    is_human_reviewed: Optional[bool] = None
    is_match: Optional[bool] = None
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    comments: Optional[str] = None

def load_query(filename: str) -> str:
    if filename in QUERY_CACHE:
        return QUERY_CACHE[filename]
    
    # Fallback to disk if not in cache (e.g. added after startup)
    path = os.path.join(os.path.dirname(__file__), "sql", filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            content = f.read()
            QUERY_CACHE[filename] = content
            return content
    
    raise HTTPException(status_code=500, detail=f"Query file {filename} not found.")

@app.get("/api/decisions")
def get_decisions(status: str = Query('pending'), search: str = Query(None), page: int = Query(1, ge=1)):
    search_string = f"%{search}%" if search else None
    
    limit = 50
    offset = (page - 1) * limit
    
    status_to_sql = {
        'pending': 'get_decisions_pending.sql',
        'reviewed': 'get_decisions_reviewed.sql',
        'auto_approved': 'get_decisions_auto_approved.sql',
        'all': 'get_decisions_all.sql'
    }
    sql_file = status_to_sql.get(status, 'get_decisions_all.sql')
    final_query = load_query(sql_file)
    
    query_params = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
        bigquery.ScalarQueryParameter("search", "STRING", search_string)
    ]
        
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_params,
        default_dataset=default_dataset_ref
    )
    
    query_job = client.query(final_query, job_config=job_config)
    results = query_job.result()
    
    rows = []
    for row in results:
        r = dict(row)
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None
        r['updated_at'] = r['updated_at'].isoformat() if r['updated_at'] else None
        rows.append(r)
        
    return rows

@app.get("/api/decisions/customer/{customer_part_number:path}")
def get_decisions_by_customer(customer_part_number: str):
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
        ],
        default_dataset=default_dataset_ref
    )
    
    query = load_query("get_decisions_by_customer.sql")
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    rows = []
    for row in results:
        r = dict(row)
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None
        r['updated_at'] = r['updated_at'].isoformat() if r['updated_at'] else None
        rows.append(r)
        
    return rows

@app.get("/api/decisions/{id:path}")
def get_decision(id: str):
    parts = id.split('|')
    customer_part_number = parts[0]
    supplier_part_number = parts[1] if len(parts) > 1 and parts[1] != '' else None
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
            bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
        ],
        default_dataset=default_dataset_ref
    )
    
    query = load_query("get_decision_by_id.sql")
    query_job = client.query(query, job_config=job_config)
    rows = list(query_job.result())
    
    if rows:
        r = dict(rows[0])
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None
        r['updated_at'] = r['updated_at'].isoformat() if r['updated_at'] else None
        return r
    else:
        return None

@app.patch("/api/decisions/{id:path}")
def update_decision(id: str, updates: DecisionUpdate):
    parts = id.split('|')
    customer_part_number = parts[0]
    supplier_part_number = parts[1] if len(parts) > 1 and parts[1] != '' else None
    
    if updates.is_human_reviewed or updates.comments is not None:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
                bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
            ],
            default_dataset=default_dataset_ref
        )
        
        q_get = load_query("get_agent_decision.sql")
        existing = list(client.query(q_get, job_config=job_config).result())
        
        q_get_human = load_query("get_human_decision.sql")
        human_existing = list(client.query(q_get_human, job_config=job_config).result())
        
        final_decision = updates.decision if updates.decision is not None else (human_existing[0].decision if human_existing else (existing[0].decision if existing else 'MATCH'))
        final_match = updates.is_match if updates.is_match is not None else (human_existing[0].is_match if human_existing else (existing[0].is_match if existing else True))
        final_reasoning = updates.reasoning if updates.reasoning is not None else (human_existing[0].reasoning if human_existing else (existing[0].reasoning if existing else 'Human Reviewed'))
        final_comments = updates.comments if updates.comments is not None else (human_existing[0].comments if human_existing else None)
        
        merge_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
                bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
                bigquery.ScalarQueryParameter("decision", "STRING", final_decision),
                bigquery.ScalarQueryParameter("isMatch", "BOOL", final_match),
                bigquery.ScalarQueryParameter("reasoning", "STRING", final_reasoning),
                bigquery.ScalarQueryParameter("comments", "STRING", final_comments),
            ],
            default_dataset=default_dataset_ref
        )
        
        if updates.is_human_reviewed:
            q_transaction = load_query("update_decision_tx_human_reviewed.sql")
        else:
            q_transaction = load_query("update_decision_tx_pending.sql")
            
        client.query(q_transaction, job_config=merge_config).result()
            
    if updates.undo_review:
        undo_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
                bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
            ],
            default_dataset=default_dataset_ref
        )
        
        q_undo_tx = load_query("undo_decision_tx.sql")
        client.query(q_undo_tx, job_config=undo_config).result()
        
    return get_decision(id)

@app.get("/")
def read_root():
    with open("index.html") as f:
        return HTMLResponse(f.read())
