ALTER TABLE {{ table_name }} ADD COLUMN "processed_at" TIMESTAMP;
UPDATE {{ table_name }} SET "processed_at" = current_timestamp;
