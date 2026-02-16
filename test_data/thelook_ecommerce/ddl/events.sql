CREATE TABLE `biglake-iceberg-datalake.bronze.events`
WITH CONNECTION `biglake-iceberg-datalake.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-iceberg-datalake-iceberg/bronze/events'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS INT64) AS user_id,
    CAST(NULL AS INT64) AS sequence_number,
    CAST(NULL AS STRING) AS session_id,
    CAST(NULL AS TIMESTAMP) AS created_at,
    CAST(NULL AS STRING) AS ip_address,
    CAST(NULL AS STRING) AS city,
    CAST(NULL AS STRING) AS state,
    CAST(NULL AS STRING) AS postal_code,
    CAST(NULL AS STRING) AS browser,
    CAST(NULL AS STRING) AS traffic_source,
    CAST(NULL AS STRING) AS uri,
    CAST(NULL AS STRING) AS event_type
WHERE FALSE;
