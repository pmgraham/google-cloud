SELECT
    column_name,
    column_type,
    approx_unique,
    null_percentage::FLOAT AS null_percentage,
    min,
    max,
    avg
FROM (SUMMARIZE SELECT * FROM {{ table_name }})
