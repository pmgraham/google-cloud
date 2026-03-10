import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from google.cloud import bigquery
from google import genai

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

try:
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location='us-central1')
except Exception as e:
    print(f"Warning: Could not initialize GenAI client: {e}")
    genai_client = None

# Serve static files from the 'static' directory
# Mount it later to allow index.html at root

class DecisionRequest(BaseModel):
    customer_part_number: str
    supplier_part_number: str
    decision: str
    is_match: bool
    reasoning: str

@app.get("/api/matches")
async def get_matches(sql_filter: str = None):
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
    
    where_clause = "(d.decision = 'REQUIRES_HUMAN_REVIEW' OR d.decision IS NULL)"
    if sql_filter:
        where_clause += f" AND ({sql_filter})"
        
    query = f"""
        SELECT 
            d.customer_part_number,
            d.supplier_part_number,
            d.decision,
            d.is_match,
            d.reasoning,
            c.part_description as customer_description,
            s.part_description as supplier_description,
            c.part_type as c_part_type, c.material as c_material, c.grade as c_grade, c.size_value as c_size, c.size_unit as c_size_unit, c.thread_pitch as c_thread_pitch, c.length_value as c_length, c.length_unit as c_length_unit, c.standard_ref as c_standard_ref,
            s.part_type as s_part_type, s.material as s_material, s.grade as s_grade, s.size_value as s_size, s.size_unit as s_size_unit, s.thread_pitch as s_thread_pitch, s.length_value as s_length, s.length_unit as s_length_unit, s.standard_ref as s_standard_ref,
            q.rrf_score
        FROM `{PROJECT_ID}.{DATASET}.agent_decisions` d
        LEFT JOIN `{PROJECT_ID}.{DATASET}.all_parts_enriched` c
            ON d.customer_part_number = c.part_number AND LOWER(c.source) = 'customer'
        LEFT JOIN `{PROJECT_ID}.{DATASET}.all_parts_enriched` s
            ON d.supplier_part_number = s.part_number AND LOWER(s.source) != 'customer'
        LEFT JOIN `{PROJECT_ID}.{DATASET}.agent_review_queue` q
            ON d.customer_part_number = q.customer_part_number AND d.supplier_part_number = q.supplier_part_number
        WHERE {where_clause}
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
                "rrf_score": row.rrf_score,
                "customer_description": row.customer_description,
                "supplier_description": row.supplier_description,
                "c_attributes": {
                    "type": row.c_part_type,
                    "material": row.c_material,
                    "grade": row.c_grade,
                    "size": f"{row.c_size} {row.c_size_unit}".strip() if row.c_size else None,
                    "thread_pitch": row.c_thread_pitch,
                    "length": f"{row.c_length} {row.c_length_unit}".strip() if row.c_length else None,
                    "standard": row.c_standard_ref
                },
                "s_attributes": {
                    "type": row.s_part_type,
                    "material": row.s_material,
                    "grade": row.s_grade,
                    "size": f"{row.s_size} {row.s_size_unit}".strip() if row.s_size else None,
                    "thread_pitch": row.s_thread_pitch,
                    "length": f"{row.s_length} {row.s_length_unit}".strip() if row.s_length else None,
                    "standard": row.s_standard_ref
                }
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

class GeminiCommandRequest(BaseModel):
    command: str

class GeminiAction(BaseModel):
    action: str = Field(description="The action taking place. Options: 'filter_list', 'bulk_accept', 'bulk_reject', 'clear_filter'")
    sql_filter: str | None = Field(description="A valid BigQuery SQL WHERE clause component using the aliases `c` (customer part), `s` (supplier part), `d` (agent_decisions), or `q` (agent_review_queue) to filter the results based on the user's command. For example: `LOWER(c.material) = 'stainless steel' AND q.rrf_score >= 0.08`. Use safe syntax. Return null if action is clear_filter. IMPORTANT: do not include the WHERE keyword itself, just the conditions. Date fields should not be filtered. DO not filter on d.decision as it is already filtered in the main query.")
    message: str = Field(description="A short natural language response to display back to the user.")

@app.post("/api/gemini_command")
async def process_gemini_command(req: GeminiCommandRequest):
    if not genai_client:
        raise HTTPException(status_code=500, detail="GenAI client not initialized")

    prompt = f"""
    The user is managing a queue of matched industrial parts. 
    You must map their natural language command to a specific action and optional SQL filter.
    
    Database Context:
    - Table aliases: `d` (agent_decisions), `c` (customer parts from all_parts_enriched), `s` (supplier parts from all_parts_enriched), `q` (agent_review_queue).
    - Confidence scores: `q.rrf_score`. High confidence is >= 0.08. Medium is >= 0.03. Low is < 0.03.
    - Attributes available on `c` and `s`: `part_type`, `material`, `grade`, `size_value`, `size_unit`, `thread_pitch`, `length_value`, `length_unit`, `standard_ref`, `part_description`.
    - `d.is_match` (boolean), `d.decision` (string), `d.reasoning` (string).
    
    User Command: "{req.command}"
    """
    
    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiAction,
                temperature=0,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class BulkDecisionRequest(BaseModel):
    decision: str
    is_match: bool
    sql_filter: str | None = None

@app.post("/api/bulk_decide")
async def bulk_decide(req: BulkDecisionRequest):
    if not bq_client:
        raise HTTPException(status_code=500, detail="BigQuery client not initialized")
        
    where_clause = "(d.decision = 'REQUIRES_HUMAN_REVIEW' OR d.decision IS NULL)"
    if req.sql_filter:
        where_clause += f" AND ({req.sql_filter})"
        
    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET}.agent_decisions` d_main
        SET decision = @decision, is_match = @is_match
        WHERE EXISTS (
            SELECT 1
            FROM `{PROJECT_ID}.{DATASET}.agent_decisions` d
            LEFT JOIN `{PROJECT_ID}.{DATASET}.all_parts_enriched` c
                ON d.customer_part_number = c.part_number AND LOWER(c.source) = 'customer'
            LEFT JOIN `{PROJECT_ID}.{DATASET}.all_parts_enriched` s
                ON d.supplier_part_number = s.part_number AND LOWER(s.source) != 'customer'
            LEFT JOIN `{PROJECT_ID}.{DATASET}.agent_review_queue` q
                ON d.customer_part_number = q.customer_part_number AND d.supplier_part_number = q.supplier_part_number
            WHERE d.customer_part_number = d_main.customer_part_number 
              AND d.supplier_part_number = d_main.supplier_part_number
              AND {where_clause}
        )
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("decision", "STRING", req.decision),
            bigquery.ScalarQueryParameter("is_match", "BOOL", req.is_match),
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
