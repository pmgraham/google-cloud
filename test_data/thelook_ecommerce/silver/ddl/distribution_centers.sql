CREATE TABLE `biglake-iceberg-datalake.silver.distribution_centers`
(
    id INT64,
    name STRING,
    city STRING,
    state STRING,
    latitude FLOAT64,
    longitude FLOAT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-iceberg-datalake.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-iceberg-datalake-iceberg/silver/distribution_centers'
);
