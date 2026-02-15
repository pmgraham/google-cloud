CREATE TABLE `biglake-pipeline-test1.silver.products`
(
    id INT64,
    cost FLOAT64,
    category STRING,
    name STRING,
    brand STRING,
    retail_price FLOAT64,
    department STRING,
    sku STRING,
    distribution_center_id INT64,
    silver_loaded_at TIMESTAMP
)
WITH CONNECTION `biglake-pipeline-test1.US.biglake-iceberg`
OPTIONS (
    file_format = 'PARQUET',
    table_format = 'ICEBERG',
    storage_uri = 'gs://biglake-pipeline-test1-iceberg/silver/products'
);
