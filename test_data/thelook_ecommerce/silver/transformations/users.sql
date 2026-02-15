-- Bronze → Silver transformation: users
-- Deduplicates by id, casts types, expands gender M/F, parses timestamps

INSERT INTO `biglake-pipeline-test1.silver.users`
(id, first_name, last_name, email, age, gender, state, street_address,
 postal_code, city, country, latitude, longitude, traffic_source, created_at, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `biglake-pipeline-test1.bronze.users`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(id AS INT64) AS id,

    CASE
        WHEN TRIM(UPPER(first_name)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(first_name))
    END AS first_name,

    CASE
        WHEN TRIM(UPPER(last_name)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(last_name))
    END AS last_name,

    LOWER(TRIM(email)) AS email,
    SAFE_CAST(age AS INT64) AS age,

    CASE
        WHEN TRIM(UPPER(gender)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        WHEN TRIM(UPPER(gender)) IN ('M', 'MALE') THEN 'Male'
        WHEN TRIM(UPPER(gender)) IN ('F', 'FEMALE') THEN 'Female'
        ELSE INITCAP(TRIM(gender))
    END AS gender,

    CASE
        WHEN TRIM(UPPER(state)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(state))
    END AS state,

    CASE
        WHEN TRIM(UPPER(street_address)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE TRIM(street_address)
    END AS street_address,

    CASE
        WHEN TRIM(UPPER(postal_code)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE TRIM(postal_code)
    END AS postal_code,

    CASE
        WHEN TRIM(UPPER(city)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(city))
    END AS city,

    CASE
        WHEN TRIM(UPPER(country)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(country))
    END AS country,

    latitude,
    longitude,

    CASE
        WHEN TRIM(UPPER(traffic_source)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(traffic_source))
    END AS traffic_source,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(created_at))
    ) AS created_at,

    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
