-- Bronze → Silver transformation: products
-- Deduplicates by id, casts types, standardizes strings
-- Drops cost_value_type, retail_price_value_type (redundant — agent already extracted numeric values)

INSERT INTO `biglake-pipeline-test1.silver.products`
(id, cost, category, name, brand, retail_price, department, sku, distribution_center_id, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `biglake-pipeline-test1.bronze.products`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(id AS INT64) AS id,
    cost,

    CASE
        WHEN TRIM(UPPER(category)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(category))
    END AS category,

    CASE
        WHEN TRIM(UPPER(name)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(name))
    END AS name,

    CASE
        WHEN TRIM(UPPER(brand)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(brand))
    END AS brand,

    retail_price,

    CASE
        WHEN TRIM(UPPER(department)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(department))
    END AS department,

    UPPER(TRIM(sku)) AS sku,
    SAFE_CAST(distribution_center_id AS INT64) AS distribution_center_id,
    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
