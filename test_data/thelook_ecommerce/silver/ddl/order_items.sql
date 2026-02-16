CREATE TABLE `biglake-iceberg-datalake.silver.order_items`
(
    id INT64,
    order_id INT64,
    user_id INT64,
    product_id INT64,
    inventory_item_id INT64,
    status STRING,
    created_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    returned_at TIMESTAMP,
    sale_price FLOAT64,
    sale_price_value_type STRING,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-iceberg-datalake.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-iceberg-datalake-iceberg/silver/order_items'
);
