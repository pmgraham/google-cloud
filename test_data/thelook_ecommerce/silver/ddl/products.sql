CREATE TABLE `__PROJECT_ID__.silver.products`
(
    id INT64,
    cost FLOAT64,
    category STRING,
    name STRING,
    brand STRING,
    retail_price FLOAT64,
    department STRING,
    sku STRING,
    distribution_center_id INT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `__PROJECT_ID__.__REGION__.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://__ICEBERG_BUCKET_NAME__/silver/products'
);
