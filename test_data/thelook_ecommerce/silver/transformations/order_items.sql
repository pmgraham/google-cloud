-- Bronze → Silver transformation: order_items
-- Deduplicates by id, casts types, parses timestamps
-- Keeps sale_price_value_type (needed for gold layer currency conversion)

INSERT INTO `biglake-pipeline-test1.silver.order_items`
(id, order_id, user_id, product_id, inventory_item_id, status,
 created_at, shipped_at, delivered_at, returned_at, sale_price,
 sale_price_value_type, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `biglake-pipeline-test1.bronze.order_items`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(id AS INT64) AS id,
    SAFE_CAST(order_id AS INT64) AS order_id,
    SAFE_CAST(user_id AS INT64) AS user_id,
    SAFE_CAST(product_id AS INT64) AS product_id,
    SAFE_CAST(inventory_item_id AS INT64) AS inventory_item_id,

    CASE
        WHEN TRIM(UPPER(status)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(status))
    END AS status,

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
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(shipped_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(shipped_at))
    ) AS shipped_at,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(delivered_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(delivered_at))
    ) AS delivered_at,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(returned_at))
    ) AS returned_at,

    sale_price,

    CASE
        WHEN sale_price_value_type IS NOT NULL
             AND TRIM(sale_price_value_type) != ''
        THEN 'USD'
        ELSE NULL
    END AS sale_price_value_type,

    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
