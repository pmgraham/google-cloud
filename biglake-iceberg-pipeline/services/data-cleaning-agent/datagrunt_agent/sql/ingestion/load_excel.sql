CREATE OR REPLACE TABLE {{ table_name }} AS
SELECT *
FROM st_read(
    '{{ file_path }}',
    open_options = ['HEADERS=FORCE']
)
