SELECT
    "{{ column_name }}" AS value,
    COUNT(*) AS occurrence_count
FROM {{ table_name }}
WHERE LOWER(TRIM("{{ column_name }}"::VARCHAR)) IN ('null', 'none', 'n/a', 'na', '-', '', '#n/a', 'nan', 'missing')
GROUP BY 1
ORDER BY 2 DESC
