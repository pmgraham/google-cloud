CREATE OR REPLACE TABLE {{ table_name }} AS
SELECT *
FROM read_parquet('{{ file_path }}')
