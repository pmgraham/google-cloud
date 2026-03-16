BEGIN TRANSACTION;

MERGE human_decisions T
USING (SELECT 
  @customerPartNumber as customer_part_number, 
  @supplierPartNumber as supplier_part_number, 
  @decision as decision, 
  @isMatch as is_match, 
  @reasoning as reasoning,
  @comments as comments
) S
ON T.customer_part_number = S.customer_part_number 
AND (T.supplier_part_number = S.supplier_part_number OR (T.supplier_part_number IS NULL AND S.supplier_part_number IS NULL))
WHEN MATCHED THEN
  UPDATE SET decision = S.decision, is_match = S.is_match, reasoning = S.reasoning, comments = S.comments, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_part_number, supplier_part_number, decision, is_match, reasoning, comments, created_at, updated_at) 
  VALUES (S.customer_part_number, S.supplier_part_number, S.decision, S.is_match, S.reasoning, S.comments, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());

UPDATE agent_decisions
SET is_human_reviewed = TRUE, updated_at = CURRENT_TIMESTAMP()
WHERE customer_part_number = @customerPartNumber
AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL));

COMMIT TRANSACTION;
