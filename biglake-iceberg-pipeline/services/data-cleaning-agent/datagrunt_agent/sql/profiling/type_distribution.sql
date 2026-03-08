SELECT
    typeof("{{ column_name }}") AS detected_type,
    COUNT(*) AS row_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM {{ table_name }}
WHERE "{{ column_name }}" IS NOT NULL
GROUP BY typeof("{{ column_name }}")
ORDER BY row_count DESC
