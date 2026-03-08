SELECT
    COUNT(*) - COUNT(DISTINCT hash) AS approximate_duplicates
FROM (
    SELECT md5(COLUMNS(*)::VARCHAR) AS hash
    FROM {{ table_name }}
)
