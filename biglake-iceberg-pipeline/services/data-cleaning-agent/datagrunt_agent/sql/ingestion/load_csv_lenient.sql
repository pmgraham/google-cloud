CREATE OR REPLACE TABLE {{ table_name }} AS
SELECT *
FROM read_csv(
    '{{ file_path }}',
    sep = '{{ delimiter }}',
    auto_detect = true,
    strict_mode = false,
    null_padding = true,
    all_varchar = true
)
