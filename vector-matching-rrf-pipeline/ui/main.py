import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.cloud import bigquery

# Try to load local config, or use defaults
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "pipeline", "config", "customer_schema_local.json")
try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        PROJECT_ID = config.get("project_id", "pmgraham-dev-workspace")
        DATASET = config.get("dataset", "vector_matching_pipeline")
except Exception as e:
    print(f"Warning: Could not load config from {CONFIG_PATH}: {e}")
    PROJECT_ID = "pmgraham-dev-workspace"
    DATASET = "vector_matching_pipeline"

app = FastAPI(title="Agent Decisions Review UI")

# Initialize BigQuery client
try:
    bq_client = bigquery.Client(project=PROJECT_ID)
except Exception as e:
    print(f"Warning: Could not initialize BigQuery client: {e}")
    bq_client = None

# Serve static files from the 'static' directory
# Mount it later to allow index.html at root

class DecisionRequest(BaseModel):
    customer_part_number: str
    supplier_part_number: str
    decision: str
    is_match: bool
    reasoning: str

@app.get("/api/matches")
async def get_matches():
    if not bq_client:
        raise HTTPException(status_code=500, detail="BigQuery client not initialized")
    
    # We will fetch rows from agent_decisions
    # Assuming decision is initially something like 'PENDING' or we just want everything where decision != 'ACCEPTED' or 'REJECTED'
    # For now, let's fetch pending reviews. 
    # If there are none, we might want to fetch all to show something.
    query = f"""
        SELECT 
            d.customer_part_number,
            d.supplier_part_number,
            d.decision,
            d.is_match,
            d.reasoning,
            c.part_description as customer_description,
            s.part_description as supplier_description
        FROM `{PROJECT_ID}.{DATASET}.agent_decisions` d
        LEFT JOIN `{PROJECT_ID}.{DATASET}.raw_customer_parts` c
            ON d.customer_part_number = c.part_number
        LEFT JOIN `{PROJECT_ID}.{DATASET}.raw_source1_parts` s
            ON d.supplier_part_number = s.part_number
        WHERE d.decision = 'PENDING' OR d.decision IS NULL OR d.decision = 'PENDING_AGENT_REVIEW'
        ORDER BY d.customer_part_number, d.supplier_part_number
        LIMIT 100
    """
    
    # Wait, the customer parts and supplier parts join might be complex if there are multiple sources.
    # What if we just fetch from agent_decisions first? And maybe get more details if needed.
    # For simplicity, let's just get the main info from agent_decisions.
    query = f"""
        SELECT 
            d.customer_part_number,
            d.supplier_part_number,
            d.decision,
            d.is_match,
            d.reasoning,
            c.part_description as customer_description,
            s.part_description as supplier_description
        FROM `{PROJECT_ID}.{DATASET}.agent_decisions` d
        LEFT JOIN `{PROJECT_ID}.{DATASET}.raw_customer_parts` c
            ON d.customer_part_number = c.part_number
        LEFT JOIN `{PROJECT_ID}.{DATASET}.raw_source1_parts` s
            ON d.supplier_part_number = s.part_number
        WHERE d.decision = 'REQUIRES_HUMAN_REVIEW' OR d.decision IS NULL
        ORDER BY d.customer_part_number, d.supplier_part_number
        LIMIT 500
    """
    try:
        query_job = bq_client.query(query)
        results = []
        for row in query_job:
            results.append({
                "customer_part_number": row.customer_part_number,
                "supplier_part_number": row.supplier_part_number,
                "decision": row.decision,
                "is_match": row.is_match,
                "reasoning": row.reasoning,
                "customer_description": row.customer_description,
                "supplier_description": row.supplier_description,
            })
            
        # Group by customer_part_number
        grouped = {}
        for r in results:
            cpn = r["customer_part_number"]
            if cpn not in grouped:
                grouped[cpn] = {
                    "customer_part_number": cpn,
                    "customer_description": r["customer_description"],
                    "matches": []
                }
            grouped[cpn]["matches"].append(r)
            
        return {"groups": list(grouped.values())}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decide")
async def submit_decision(req: DecisionRequest):
    if not bq_client:
        raise HTTPException(status_code=500, detail="BigQuery client not initialized")
        
    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET}.agent_decisions`
        SET decision = @decision, is_match = @is_match
        WHERE customer_part_number = @cpn AND supplier_part_number = @spn
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("decision", "STRING", req.decision),
            bigquery.ScalarQueryParameter("is_match", "BOOL", req.is_match),
            bigquery.ScalarQueryParameter("cpn", "STRING", req.customer_part_number),
            bigquery.ScalarQueryParameter("spn", "STRING", req.supplier_part_number),
        ]
    )
    
    try:
        bq_client.query(query, job_config=job_config).result()
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))
