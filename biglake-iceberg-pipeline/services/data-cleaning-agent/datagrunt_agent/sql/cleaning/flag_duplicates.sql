ALTER TABLE {{ table_name }} ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false;

UPDATE {{ table_name }}
SET is_duplicate = true
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM {{ table_name }}
    GROUP BY {{ column_list }}
)
