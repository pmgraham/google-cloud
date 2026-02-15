CREATE TABLE `biglake-pipeline-test1.silver.users`
(
    id INT64,
    first_name STRING,
    last_name STRING,
    email STRING,
    age INT64,
    gender STRING,
    state STRING,
    street_address STRING,
    postal_code STRING,
    city STRING,
    country STRING,
    latitude FLOAT64,
    longitude FLOAT64,
    traffic_source STRING,
    created_at TIMESTAMP,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/silver/users'
);
