WITH schema_a AS (
    SELECT column_name, column_type
    FROM (DESCRIBE {{ table_a }})
),
schema_b AS (
    SELECT column_name, column_type
    FROM (DESCRIBE {{ table_b }})
)
SELECT
    COALESCE(a.column_name, b.column_name) AS column_name,
    a.column_type AS type_in_a,
    b.column_type AS type_in_b,
    CASE
        WHEN a.column_name IS NULL THEN 'added'
        WHEN b.column_name IS NULL THEN 'removed'
        WHEN a.column_type != b.column_type THEN 'type_changed'
        ELSE 'unchanged'
    END AS change_type
FROM schema_a a
FULL OUTER JOIN schema_b b ON a.column_name = b.column_name
WHERE a.column_name IS NULL
   OR b.column_name IS NULL
   OR a.column_type != b.column_type
ORDER BY change_type, column_name
