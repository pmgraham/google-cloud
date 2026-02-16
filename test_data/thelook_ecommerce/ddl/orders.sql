CREATE TABLE `biglake-iceberg-datalake.bronze.orders`
WITH CONNECTION `biglake-iceberg-datalake.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-iceberg-datalake-iceberg/bronze/orders'
)
AS SELECT
    CAST(NULL AS INT64) AS order_id,
    CAST(NULL AS INT64) AS user_id,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS STRING) AS gender,
    CAST(NULL AS TIMESTAMP) AS created_at,
    CAST(NULL AS TIMESTAMP) AS returned_at,
    CAST(NULL AS TIMESTAMP) AS shipped_at,
    CAST(NULL AS TIMESTAMP) AS delivered_at,
    CAST(NULL AS INT64) AS num_of_item
WHERE FALSE;
