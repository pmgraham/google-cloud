SELECT
    {{ column_list }},
    COUNT(*) AS duplicate_count
FROM {{ table_name }}
GROUP BY {{ column_list }}
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC
LIMIT 50
