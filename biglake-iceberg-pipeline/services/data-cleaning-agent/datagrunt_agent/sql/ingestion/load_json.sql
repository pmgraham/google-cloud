CREATE OR REPLACE TABLE {{ table_name }} AS
SELECT *
FROM read_json(
    '{{ file_path }}',
    auto_detect = true,
    format = '{{ json_format }}'
)
