CREATE TABLE `biglake-pipeline-test1.bronze.inventory_items`
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/bronze/inventory_items'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS INT64) AS product_id,
    CAST(NULL AS TIMESTAMP) AS created_at,
    CAST(NULL AS TIMESTAMP) AS sold_at,
    CAST(NULL AS FLOAT64) AS cost,
    CAST(NULL AS STRING) AS product_category,
    CAST(NULL AS STRING) AS product_name,
    CAST(NULL AS STRING) AS product_brand,
    CAST(NULL AS FLOAT64) AS product_retail_price,
    CAST(NULL AS STRING) AS product_department,
    CAST(NULL AS STRING) AS product_sku,
    CAST(NULL AS INT64) AS product_distribution_center_id
WHERE FALSE;
