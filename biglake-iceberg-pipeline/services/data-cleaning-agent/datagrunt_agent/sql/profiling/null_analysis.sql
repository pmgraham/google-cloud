SELECT
    '{{ column_name }}' AS column_name,
    COUNT(*) AS total_rows,
    COUNT("{{ column_name }}") AS non_null_count,
    COUNT(*) - COUNT("{{ column_name }}") AS null_count,
    ROUND((COUNT(*) - COUNT("{{ column_name }}")) * 100.0 / COUNT(*), 2) AS null_percentage
FROM {{ table_name }}
