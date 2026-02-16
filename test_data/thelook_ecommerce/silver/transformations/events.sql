-- Bronze → Silver transformation: events
-- Deduplicates by id, casts types, standardizes strings, parses timestamps

INSERT INTO `biglake-iceberg-datalake.silver.events`
(id, user_id, sequence_number, session_id, created_at, ip_address,
 city, state, postal_code, browser, traffic_source, uri, event_type, silver_loaded_at)

WITH deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY SAFE_CAST(id AS INT64)
            ORDER BY processed_at DESC
        ) AS row_rank
    FROM `biglake-iceberg-datalake.bronze.events`
    WHERE is_duplicate_in_file = FALSE
)
SELECT
    SAFE_CAST(id AS INT64) AS id,
    SAFE_CAST(user_id AS INT64) AS user_id,
    SAFE_CAST(sequence_number AS INT64) AS sequence_number,

    TRIM(session_id) AS session_id,

    COALESCE(
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%Y/%m/%d %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m/%d/%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%m-%d-%Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%b %d %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%d %b %Y %H:%M:%S', TRIM(created_at)),
        SAFE.PARSE_TIMESTAMP('%B %d, %Y %H:%M:%S', TRIM(created_at))
    ) AS created_at,

    TRIM(ip_address) AS ip_address,

    CASE
        WHEN TRIM(UPPER(city)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(city))
    END AS city,

    CASE
        WHEN TRIM(UPPER(state)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(state))
    END AS state,

    TRIM(postal_code) AS postal_code,

    CASE
        WHEN TRIM(UPPER(browser)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(browser))
    END AS browser,

    CASE
        WHEN TRIM(UPPER(traffic_source)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE INITCAP(TRIM(traffic_source))
    END AS traffic_source,

    TRIM(uri) AS uri,

    CASE
        WHEN TRIM(UPPER(event_type)) IN ('N/A','NA','NONE','NULL','-','--','MISSING','#N/A','')
        THEN NULL
        ELSE LOWER(TRIM(event_type))
    END AS event_type,

    CURRENT_TIMESTAMP() AS silver_loaded_at

FROM deduplicated
WHERE row_rank = 1;
