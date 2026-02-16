CREATE TABLE `__PROJECT_ID__.bronze.products`
WITH CONNECTION `__PROJECT_ID__.__REGION__.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://__ICEBERG_BUCKET_NAME__/bronze/products'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS FLOAT64) AS cost,
    CAST(NULL AS STRING) AS category,
    CAST(NULL AS STRING) AS name,
    CAST(NULL AS STRING) AS brand,
    CAST(NULL AS FLOAT64) AS retail_price,
    CAST(NULL AS STRING) AS department,
    CAST(NULL AS STRING) AS sku,
    CAST(NULL AS INT64) AS distribution_center_id
WHERE FALSE;
