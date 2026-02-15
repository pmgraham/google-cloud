INSERT INTO `biglake-pipeline-test1.silver.distribution_centers`
(id, name, city, state, latitude, longitude, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `biglake-pipeline-test1.bronze.distribution_centers`
    WHERE is_duplicate_in_file = FALSE
),

parsed AS (
    SELECT
        SAFE_CAST(id AS INT64) AS id,

        CASE
            WHEN TRIM(UPPER(name)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
            THEN NULL
            ELSE INITCAP(TRIM(name))
        END AS name,

        TRIM(name) AS raw_name,
        latitude,
        longitude
    FROM deduplicated
    WHERE row_rank = 1
)

SELECT
    id,
    name,

    INITCAP(TRIM(
        REGEXP_REPLACE(raw_name, r'\s+[A-Z]{2}(/[A-Z]{2})?$', '')
    )) AS city,

    UPPER(TRIM(
        REGEXP_EXTRACT(raw_name, r'\s+([A-Z]{2}(?:/[A-Z]{2})?)$')
    )) AS state,

    latitude,
    longitude,
    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM parsed;
