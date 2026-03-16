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
  COALESCE(c.part_description, q.customer_description) as customer_description,
  'Customer' as customer_manufacturer,
  c.part_type as customer_category,
  COALESCE(s.part_description, q.supplier_description) as supplier_description,
  COALESCE(s.source, q.supplier) as supplier_manufacturer,
  s.part_type as supplier_category,
  CAST(NULL AS FLOAT64) as supplier_price
FROM agent_decisions d
LEFT JOIN agent_review_queue q 
  ON d.customer_part_number = q.customer_part_number 
  AND (d.supplier_part_number = q.supplier_part_number OR (d.supplier_part_number IS NULL AND q.supplier_part_number IS NULL))
LEFT JOIN all_parts_enriched c
  ON d.customer_part_number = c.part_number AND c.source = 'Customer'
LEFT JOIN all_parts_enriched s
  ON d.supplier_part_number = s.part_number AND s.source = q.supplier
LEFT JOIN human_decisions h
  ON d.customer_part_number = h.customer_part_number
  AND (d.supplier_part_number = h.supplier_part_number OR (d.supplier_part_number IS NULL AND h.supplier_part_number IS NULL))
WHERE d.is_human_reviewed = FALSE
  AND (@search IS NULL OR 
    LOWER(d.customer_part_number) LIKE LOWER(@search) OR 
    LOWER(d.supplier_part_number) LIKE LOWER(@search) OR 
    LOWER(q.customer_description) LIKE LOWER(@search) OR 
    LOWER(q.supplier_description) LIKE LOWER(@search)
  )
ORDER BY d.customer_part_number ASC
LIMIT @limit OFFSET @offset
