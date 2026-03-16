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
WHERE (@search IS NULL OR 
  LOWER(a.customer_part_number) LIKE LOWER(@search) OR 
  LOWER(a.supplier_part_number) LIKE LOWER(@search) OR 
  LOWER(a.customer_description) LIKE LOWER(@search) OR 
  LOWER(a.supplier_description) LIKE LOWER(@search)
)
ORDER BY a.customer_part_number ASC
LIMIT @limit OFFSET @offset
