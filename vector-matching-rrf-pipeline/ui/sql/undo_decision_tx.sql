BEGIN TRANSACTION;

UPDATE agent_decisions
SET is_human_reviewed = FALSE, updated_at = CURRENT_TIMESTAMP()
WHERE customer_part_number = @customerPartNumber
AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL));

UPDATE human_decisions
SET decision = NULL, is_match = NULL, reasoning = NULL, updated_at = CURRENT_TIMESTAMP()
WHERE customer_part_number = @customerPartNumber
AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
AND TRIM(IFNULL(comments, '')) != '';

DELETE FROM human_decisions
WHERE customer_part_number = @customerPartNumber
AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
AND TRIM(IFNULL(comments, '')) = '';

COMMIT TRANSACTION;
