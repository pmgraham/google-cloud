CREATE TABLE `biglake-pipeline-test1.silver.distribution_centers`
(
    id INT64,
    name STRING,
    city STRING,
    state STRING,
    latitude FLOAT64,
    longitude FLOAT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/silver/distribution_centers'
);
