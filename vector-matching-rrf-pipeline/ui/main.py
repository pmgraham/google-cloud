import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.cloud import bigquery

app = FastAPI()

project_id = os.environ.get("PROJECT_ID", "pmgraham-dev-workspace")
dataset_id = os.environ.get("DATASET_ID", "vector_matching_pipeline")

client = bigquery.Client(project=project_id)

class DecisionUpdate(BaseModel):
    is_human_reviewed: Optional[bool] = None
    is_match: Optional[bool] = None
    decision: Optional[str] = None
    reasoning: Optional[str] = None

def get_search_condition(search: str):
    if not search:
        return "1=1"
    return """(
      LOWER(customer_part_number) LIKE LOWER(@search) OR 
      LOWER(supplier_part_number) LIKE LOWER(@search) OR 
      LOWER(customer_description) LIKE LOWER(@search) OR 
      LOWER(supplier_description) LIKE LOWER(@search)
    )"""

@app.get("/api/decisions")
def get_decisions(status: str = Query('pending'), search: str = Query(None), page: int = Query(1, ge=1)):
    search_string = f"%{search}%" if search else None
    
    limit = 50
    offset = (page - 1) * limit
    
    if status == 'pending':
        query = f"""
            SELECT 
              CONCAT(d.customer_part_number, '|', IFNULL(d.supplier_part_number, '')) as id,
              d.customer_part_number,
              d.decision,
              d.is_match,
              d.supplier_part_number,
              d.reasoning,
              d.is_human_reviewed,
              d.created_at,
              d.updated_at,
              q.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              q.supplier_description as supplier_description,
              q.supplier as supplier_manufacturer,
              q.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.agent_decisions` d
            LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
              ON d.customer_part_number = q.customer_part_number 
              AND (d.supplier_part_number = q.supplier_part_number OR (d.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
            WHERE d.is_human_reviewed = FALSE
        """
    elif status == 'reviewed':
        query = f"""
            SELECT 
              CONCAT(h.customer_part_number, '|', IFNULL(h.supplier_part_number, '')) as id,
              h.customer_part_number,
              h.decision,
              h.is_match,
              h.supplier_part_number,
              h.reasoning,
              TRUE as is_human_reviewed,
              h.created_at,
              h.updated_at,
              q.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              q.supplier_description as supplier_description,
              q.supplier as supplier_manufacturer,
              q.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.human_decisions` h
            LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
              ON h.customer_part_number = q.customer_part_number 
              AND (h.supplier_part_number = q.supplier_part_number OR (h.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
            WHERE 1=1
        """
    elif status == 'auto_approved':
        query = f"""
            SELECT 
              CONCAT(a.customer_part_number, '|', IFNULL(a.supplier_part_number, '')) as id,
              a.customer_part_number,
              'MATCH' as decision,
              TRUE as is_match,
              a.supplier_part_number,
              'Auto-approved based on high confidence pipeline score.' as reasoning,
              FALSE as is_human_reviewed,
              a.created_at as created_at,
              a.created_at as updated_at,
              a.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              a.supplier_description as supplier_description,
              a.supplier as supplier_manufacturer,
              a.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.auto_approved_matches` a
            WHERE 1=1
        """
    else: # all
        query = f"""
            SELECT 
              CONCAT(d.customer_part_number, '|', IFNULL(d.supplier_part_number, '')) as id,
              d.customer_part_number,
              d.decision,
              d.is_match,
              d.supplier_part_number,
              d.reasoning,
              d.is_human_reviewed,
              d.created_at,
              d.updated_at,
              q.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              q.supplier_description as supplier_description,
              q.supplier as supplier_manufacturer,
              q.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.agent_decisions` d
            LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
              ON d.customer_part_number = q.customer_part_number 
              AND (d.supplier_part_number = q.supplier_part_number OR (d.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
            WHERE d.is_human_reviewed = FALSE
            
            UNION ALL
            
            SELECT 
              CONCAT(h.customer_part_number, '|', IFNULL(h.supplier_part_number, '')) as id,
              h.customer_part_number,
              h.decision,
              h.is_match,
              h.supplier_part_number,
              h.reasoning,
              TRUE as is_human_reviewed,
              h.created_at,
              h.updated_at,
              q.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              q.supplier_description as supplier_description,
              q.supplier as supplier_manufacturer,
              q.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.human_decisions` h
            LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
              ON h.customer_part_number = q.customer_part_number 
              AND (h.supplier_part_number = q.supplier_part_number OR (h.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
              
            UNION ALL
            
            SELECT 
              CONCAT(a.customer_part_number, '|', IFNULL(a.supplier_part_number, '')) as id,
              a.customer_part_number,
              'MATCH' as decision,
              TRUE as is_match,
              a.supplier_part_number,
              'Auto-approved based on high confidence pipeline score.' as reasoning,
              FALSE as is_human_reviewed,
              a.created_at as created_at,
              a.created_at as updated_at,
              a.customer_description as customer_description,
              CAST(NULL AS STRING) as customer_manufacturer,
              CAST(NULL AS STRING) as customer_category,
              a.supplier_description as supplier_description,
              a.supplier as supplier_manufacturer,
              a.part_type as supplier_category,
              CAST(NULL AS FLOAT64) as supplier_price
            FROM `{project_id}.{dataset_id}.auto_approved_matches` a
        """

    final_query = f"""
      SELECT * FROM ({query})
      WHERE {get_search_condition(search_string)}
      ORDER BY customer_part_number ASC
      LIMIT @limit OFFSET @offset
    """
    
    query_params = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    if search_string:
        query_params.append(bigquery.ScalarQueryParameter("search", "STRING", search_string))
        
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_params
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

@app.get("/api/decisions/{id:path}")
def get_decision(id: str):
    parts = id.split('|')
    customer_part_number = parts[0]
    supplier_part_number = parts[1] if len(parts) > 1 and parts[1] != '' else None
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
            bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
        ]
    )

    q_human = f"""
      SELECT 
        CONCAT(h.customer_part_number, '|', IFNULL(h.supplier_part_number, '')) as id,
        h.customer_part_number,
        h.decision,
        h.is_match,
        h.supplier_part_number,
        h.reasoning,
        TRUE as is_human_reviewed,
        h.created_at,
        h.updated_at,
        q.customer_description as customer_description,
        CAST(NULL AS STRING) as customer_manufacturer,
        CAST(NULL AS STRING) as customer_category,
        q.supplier_description as supplier_description,
        q.supplier as supplier_manufacturer,
        q.part_type as supplier_category,
        CAST(NULL AS FLOAT64) as supplier_price
      FROM `{project_id}.{dataset_id}.human_decisions` h
      LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
        ON h.customer_part_number = q.customer_part_number 
        AND (h.supplier_part_number = q.supplier_part_number OR (h.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
      WHERE h.customer_part_number = @customerPartNumber 
      AND (h.supplier_part_number = @supplierPartNumber OR (h.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
    """
    rows = list(client.query(q_human, job_config=job_config).result())
    
    if not rows:
        q_agent = f"""
          SELECT 
            CONCAT(d.customer_part_number, '|', IFNULL(d.supplier_part_number, '')) as id,
            d.customer_part_number,
            d.decision,
            d.is_match,
            d.supplier_part_number,
            d.reasoning,
            d.is_human_reviewed,
            d.created_at,
            d.updated_at,
            q.customer_description as customer_description,
            CAST(NULL AS STRING) as customer_manufacturer,
            CAST(NULL AS STRING) as customer_category,
            q.supplier_description as supplier_description,
            q.supplier as supplier_manufacturer,
            q.part_type as supplier_category,
            CAST(NULL AS FLOAT64) as supplier_price
          FROM `{project_id}.{dataset_id}.agent_decisions` d
          LEFT JOIN `{project_id}.{dataset_id}.agent_review_queue` q 
            ON d.customer_part_number = q.customer_part_number 
            AND (d.supplier_part_number = q.supplier_part_number OR (d.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
          WHERE d.customer_part_number = @customerPartNumber 
          AND (d.supplier_part_number = @supplierPartNumber OR (d.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
        """
        rows = list(client.query(q_agent, job_config=job_config).result())
        
    if not rows:
        q_auto = f"""
          SELECT 
            CONCAT(a.customer_part_number, '|', IFNULL(a.supplier_part_number, '')) as id,
            a.customer_part_number,
            'MATCH' as decision,
            TRUE as is_match,
            a.supplier_part_number,
            'Auto-approved based on high confidence pipeline score.' as reasoning,
            FALSE as is_human_reviewed,
            a.created_at as created_at,
            a.created_at as updated_at,
            a.customer_description as customer_description,
            CAST(NULL AS STRING) as customer_manufacturer,
            CAST(NULL AS STRING) as customer_category,
            a.supplier_description as supplier_description,
            a.supplier as supplier_manufacturer,
            a.part_type as supplier_category,
            CAST(NULL AS FLOAT64) as supplier_price
          FROM `{project_id}.{dataset_id}.auto_approved_matches` a
          WHERE a.customer_part_number = @customerPartNumber 
          AND (a.supplier_part_number = @supplierPartNumber OR (a.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
        """
        rows = list(client.query(q_auto, job_config=job_config).result())
        
    if rows:
        r = dict(rows[0])
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None
        r['updated_at'] = r['updated_at'].isoformat() if r['updated_at'] else None
        return r
    else:
        raise HTTPException(status_code=404, detail="Not found")

@app.patch("/api/decisions/{id:path}")
def update_decision(id: str, updates: DecisionUpdate):
    parts = id.split('|')
    customer_part_number = parts[0]
    supplier_part_number = parts[1] if len(parts) > 1 and parts[1] != '' else None
    
    if updates.is_human_reviewed:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
                bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
            ]
        )
        q_get = f"""
            SELECT decision, is_match, reasoning 
            FROM `{project_id}.{dataset_id}.agent_decisions`
            WHERE customer_part_number = @customerPartNumber
            AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
        """
        existing = list(client.query(q_get, job_config=job_config).result())
        
        final_decision = updates.decision if updates.decision is not None else (existing[0].decision if existing else 'MATCH')
        final_match = updates.is_match if updates.is_match is not None else (existing[0].is_match if existing else True)
        final_reasoning = updates.reasoning if updates.reasoning is not None else (existing[0].reasoning if existing else 'Human Reviewed')
        
        merge_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customerPartNumber", "STRING", customer_part_number),
                bigquery.ScalarQueryParameter("supplierPartNumber", "STRING", supplier_part_number),
                bigquery.ScalarQueryParameter("decision", "STRING", final_decision),
                bigquery.ScalarQueryParameter("isMatch", "BOOL", final_match),
                bigquery.ScalarQueryParameter("reasoning", "STRING", final_reasoning),
            ]
        )
        
        q_merge = f"""
          MERGE `{project_id}.{dataset_id}.human_decisions` T
          USING (SELECT 
            @customerPartNumber as customer_part_number, 
            @supplierPartNumber as supplier_part_number, 
            @decision as decision, 
            @isMatch as is_match, 
            @reasoning as reasoning
          ) S
          ON T.customer_part_number = S.customer_part_number 
          AND (T.supplier_part_number = S.supplier_part_number OR (T.supplier_part_number IS NULL AND S.supplier_part_number IS NULL))
          WHEN MATCHED THEN
            UPDATE SET decision = S.decision, is_match = S.is_match, reasoning = S.reasoning, updated_at = CURRENT_TIMESTAMP()
          WHEN NOT MATCHED THEN
            INSERT (customer_part_number, supplier_part_number, decision, is_match, reasoning, created_at, updated_at) 
            VALUES (S.customer_part_number, S.supplier_part_number, S.decision, S.is_match, S.reasoning, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """
        client.query(q_merge, job_config=merge_config).result()
        
        q_update = f"""
          UPDATE `{project_id}.{dataset_id}.agent_decisions`
          SET is_human_reviewed = TRUE, updated_at = CURRENT_TIMESTAMP()
          WHERE customer_part_number = @customerPartNumber
          AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
        """
        client.query(q_update, job_config=job_config).result()
        
    return get_decision(id)

@app.get("/")
def read_root():
    with open("index.html") as f:
        return HTMLResponse(f.read())
