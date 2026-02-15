CREATE TABLE `biglake-pipeline-test1.silver.events`
(
    id INT64,
    user_id INT64,
    sequence_number INT64,
    session_id STRING,
    created_at TIMESTAMP,
    ip_address STRING,
    city STRING,
    state STRING,
    postal_code STRING,
    browser STRING,
    traffic_source STRING,
    uri STRING,
    event_type STRING,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/silver/events'
);
