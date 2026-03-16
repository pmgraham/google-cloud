SELECT decision, is_match, reasoning, comments
FROM human_decisions
WHERE customer_part_number = @customerPartNumber
AND (supplier_part_number = @supplierPartNumber OR (supplier_part_number IS NULL AND @supplierPartNumber IS NULL))
