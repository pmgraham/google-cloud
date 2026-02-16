CREATE TABLE `biglake-iceberg-datalake.bronze.users`
WITH CONNECTION `biglake-iceberg-datalake.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-iceberg-datalake-iceberg/bronze/users'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS STRING) AS first_name,
    CAST(NULL AS STRING) AS last_name,
    CAST(NULL AS STRING) AS email,
    CAST(NULL AS INT64) AS age,
    CAST(NULL AS STRING) AS gender,
    CAST(NULL AS STRING) AS state,
    CAST(NULL AS STRING) AS street_address,
    CAST(NULL AS STRING) AS postal_code,
    CAST(NULL AS STRING) AS city,
    CAST(NULL AS STRING) AS country,
    CAST(NULL AS FLOAT64) AS latitude,
    CAST(NULL AS FLOAT64) AS longitude,
    CAST(NULL AS STRING) AS traffic_source,
    CAST(NULL AS TIMESTAMP) AS created_at
WHERE FALSE;
