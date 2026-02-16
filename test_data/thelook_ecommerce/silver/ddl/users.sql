CREATE TABLE `__PROJECT_ID__.silver.users`
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
WITH CONNECTION `__PROJECT_ID__.__REGION__.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://__ICEBERG_BUCKET_NAME__/silver/users'
);
