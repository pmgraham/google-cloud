CREATE TABLE `biglake-pipeline-test1.bronze.distribution_centers`
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/bronze/distribution_centers'
)
AS SELECT
    CAST(NULL AS INT64) AS id,
    CAST(NULL AS STRING) AS name,
    CAST(NULL AS FLOAT64) AS latitude,
    CAST(NULL AS FLOAT64) AS longitude
WHERE FALSE;
