CREATE TABLE `__PROJECT_ID__.silver.orders`
(
    order_id INT64,
    user_id INT64,
    status STRING,
    gender STRING,
    created_at TIMESTAMP,
    returned_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    num_of_item INT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `__PROJECT_ID__.__REGION__.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://__ICEBERG_BUCKET_NAME__/silver/orders'
);
