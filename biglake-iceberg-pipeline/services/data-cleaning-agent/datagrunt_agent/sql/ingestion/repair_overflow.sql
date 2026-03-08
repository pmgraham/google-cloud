CREATE OR REPLACE TABLE {{ table_name }}_repaired AS
SELECT
    {{ real_columns }},
    CASE WHEN ({{ overflow_check_expr }}) THEN true ELSE false END AS is_shifted
FROM {{ table_name }}
