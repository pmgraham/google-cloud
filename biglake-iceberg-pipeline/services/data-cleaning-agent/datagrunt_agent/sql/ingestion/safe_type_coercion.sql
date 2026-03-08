-- Analyze VARCHAR columns to determine which can be safely cast to
-- numeric or boolean types without data loss.
-- Returns one row per castable column with the recommended type.
SELECT
    column_name,
    CASE
        -- Boolean: only contains true/false/null (case-insensitive)
        WHEN non_null_count > 0
            AND non_null_count = bool_count
            THEN 'BOOLEAN'
        -- Integer: all non-null values are digit-only (no leading zeros except bare '0')
        WHEN non_null_count > 0
            AND non_null_count = integer_count
            AND leading_zero_count = 0
            THEN 'BIGINT'
        -- Float: all non-null values look numeric (digits + one dot) with no leading zeros
        WHEN non_null_count > 0
            AND non_null_count = float_count
            AND leading_zero_count = 0
            THEN 'DOUBLE'
        ELSE NULL
    END AS recommended_type
FROM (
    SELECT
        column_name,
        COUNT(*) FILTER (
            WHERE value IS NOT NULL AND TRIM(value) != ''
        ) AS non_null_count,
        COUNT(*) FILTER (
            WHERE REGEXP_MATCHES(TRIM(value), '^-?[0-9]+$')
        ) AS integer_count,
        COUNT(*) FILTER (
            WHERE REGEXP_MATCHES(TRIM(value), '^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$')
        ) AS float_count,
        COUNT(*) FILTER (
            WHERE LOWER(TRIM(value)) IN ('true', 'false')
        ) AS bool_count,
        COUNT(*) FILTER (
            WHERE REGEXP_MATCHES(TRIM(value), '^-?0[0-9]+')
        ) AS leading_zero_count
    FROM (
        {{ unpivot_query }}
    ) AS unpivoted
    GROUP BY column_name
) AS analysis
WHERE recommended_type IS NOT NULL
