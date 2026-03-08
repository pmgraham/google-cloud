SELECT
    column_name,
    column_type,
    CASE WHEN "null" = 'YES' THEN true ELSE false END AS is_nullable
FROM (DESCRIBE {{ table_name }})
