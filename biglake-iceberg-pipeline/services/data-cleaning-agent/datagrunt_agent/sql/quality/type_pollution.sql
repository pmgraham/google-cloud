SELECT
    "{{ column_name }}" AS value,
    COUNT(*) AS occurrence_count
FROM {{ table_name }}
WHERE try_cast("{{ column_name }}" AS DOUBLE) IS NULL
  AND "{{ column_name }}" IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10
