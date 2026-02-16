CREATE TABLE `__PROJECT_ID__.silver.inventory_items`
(
    id INT64,
    product_id INT64,
    created_at TIMESTAMP,
    sold_at TIMESTAMP,
    cost FLOAT64,
    product_category STRING,
    product_name STRING,
    product_brand STRING,
    product_retail_price FLOAT64,
    product_department STRING,
    product_sku STRING,
    product_distribution_center_id INT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `__PROJECT_ID__.__REGION__.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://__ICEBERG_BUCKET_NAME__/silver/inventory_items'
);
