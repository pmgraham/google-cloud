-- Bronze → Silver transformation: orders
-- Deduplicates by order_id, casts types, expands gender M/F, parses timestamps

INSERT INTO `__PROJECT_ID__.silver.orders`
(order_id, user_id, status, gender, created_at, returned_at, shipped_at, delivered_at,
 num_of_item, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(order_id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `__PROJECT_ID__.bronze.orders`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(order_id AS INT64) AS order_id,
    SAFE_CAST(user_id AS INT64) AS user_id,

    CASE
        WHEN TRIM(UPPER(status)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(status))
    END AS status,

    CASE
        WHEN TRIM(UPPER(gender)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        WHEN TRIM(UPPER(gender)) IN ('M', 'MALE') THEN 'Male'
        WHEN TRIM(UPPER(gender)) IN ('F', 'FEMALE') THEN 'Female'
        ELSE INITCAP(TRIM(gender))
    END AS gender,

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
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(returned_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(returned_at))
    ) AS returned_at,

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

    SAFE_CAST(num_of_item AS INT64) AS num_of_item,
    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
