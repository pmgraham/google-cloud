CREATE TABLE `biglake-pipeline-test1.bronze.order_items`
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/bronze/order_items'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS INT64) AS order_id,
    CAST(NULL AS INT64) AS user_id,
    CAST(NULL AS INT64) AS product_id,
    CAST(NULL AS INT64) AS inventory_item_id,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS TIMESTAMP) AS created_at,
    CAST(NULL AS TIMESTAMP) AS shipped_at,
    CAST(NULL AS TIMESTAMP) AS delivered_at,
    CAST(NULL AS TIMESTAMP) AS returned_at,
    CAST(NULL AS FLOAT64) AS sale_price
WHERE FALSE;
