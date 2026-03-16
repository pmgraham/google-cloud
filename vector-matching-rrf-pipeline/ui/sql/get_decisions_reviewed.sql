SELECT DISTINCT
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
  AND (@search IS NULL OR 
    LOWER(h.customer_part_number) LIKE LOWER(@search) OR 
    LOWER(h.supplier_part_number) LIKE LOWER(@search) OR 
    LOWER(q.customer_description) LIKE LOWER(@search) OR 
    LOWER(q.supplier_description) LIKE LOWER(@search)
  )
ORDER BY h.customer_part_number ASC
LIMIT @limit OFFSET @offset
