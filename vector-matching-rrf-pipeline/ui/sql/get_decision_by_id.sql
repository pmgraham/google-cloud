WITH all_results AS (
  SELECT 
    CONCAT(d.customer_part_number, '|', IFNULL(d.supplier_part_number, '')) as id,
    d.customer_part_number,
    d.decision,
    d.is_match,
    d.supplier_part_number,
    d.reasoning,
    h.comments as comments,
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
  FROM agent_decisions d
  LEFT JOIN agent_review_queue q 
    ON d.customer_part_number = q.customer_part_number 
    AND (d.supplier_part_number = q.supplier_part_number OR (d.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
  LEFT JOIN human_decisions h
    ON d.customer_part_number = h.customer_part_number
    AND (d.supplier_part_number = h.supplier_part_number OR (d.supplier_part_number IS NULL AND h.supplier_part_number IS NULL))
  WHERE d.is_human_reviewed = FALSE
  AND d.customer_part_number = @customerPartNumber
  AND (d.supplier_part_number = @supplierPartNumber OR (d.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
  
  UNION ALL
  
  SELECT 
    CONCAT(h.customer_part_number, '|', IFNULL(h.supplier_part_number, '')) as id,
    h.customer_part_number,
    h.decision,
    h.is_match,
    h.supplier_part_number,
    h.reasoning,
    h.comments as comments,
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
  FROM human_decisions h
  INNER JOIN agent_decisions a
    ON h.customer_part_number = a.customer_part_number 
    AND (h.supplier_part_number = a.supplier_part_number OR (h.supplier_part_number IS NULL AND a.supplier_part_number IS NULL))
  LEFT JOIN agent_review_queue q 
    ON h.customer_part_number = q.customer_part_number 
    AND (h.supplier_part_number = q.supplier_part_number OR (h.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
  WHERE a.is_human_reviewed = TRUE
  AND h.customer_part_number = @customerPartNumber
  AND (h.supplier_part_number = @supplierPartNumber OR (h.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
    
  UNION ALL
  
  SELECT 
    CONCAT(a.customer_part_number, '|', IFNULL(a.supplier_part_number, '')) as id,
    a.customer_part_number,
    'MATCH' as decision,
    TRUE as is_match,
    a.supplier_part_number,
    'Auto-approved based on high confidence pipeline score.' as reasoning,
    h.comments as comments,
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
  FROM auto_approved_matches a
  LEFT JOIN human_decisions h
    ON a.customer_part_number = h.customer_part_number
    AND (a.supplier_part_number = h.supplier_part_number OR (a.supplier_part_number IS NULL AND h.supplier_part_number IS NULL))
  WHERE a.customer_part_number = @customerPartNumber
  AND (a.supplier_part_number = @supplierPartNumber OR (a.supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
)
SELECT * FROM all_results
