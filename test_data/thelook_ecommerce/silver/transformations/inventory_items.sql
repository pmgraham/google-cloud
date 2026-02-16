-- Bronze → Silver transformation: inventory_items
-- Deduplicates by id, casts types, standardizes strings, parses timestamps
-- Drops cost_value_type, product_retail_price_value_type

INSERT INTO `__PROJECT_ID__.silver.inventory_items`
(id, product_id, created_at, sold_at, cost, product_category, product_name,
 product_brand, product_retail_price, product_department, product_sku,
 product_distribution_center_id, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `__PROJECT_ID__.bronze.inventory_items`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(id AS INT64) AS id,
    SAFE_CAST(product_id AS INT64) AS product_id,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(created_at))
    ) AS created_at,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(sold_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(sold_at))
    ) AS sold_at,

    cost,

    CASE
        WHEN TRIM(UPPER(product_category)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(product_category))
    END AS product_category,

    CASE
        WHEN TRIM(UPPER(product_name)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(product_name))
    END AS product_name,

    CASE
        WHEN TRIM(UPPER(product_brand)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(product_brand))
    END AS product_brand,

    product_retail_price,

    CASE
        WHEN TRIM(UPPER(product_department)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(product_department))
    END AS product_department,

    UPPER(TRIM(product_sku)) AS product_sku,
    SAFE_CAST(product_distribution_center_id AS INT64) AS product_distribution_center_id,
    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
