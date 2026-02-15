import logging
import uuid

from google.cloud import bigquery

from config import Config

logger = logging.getLogger(__name__)

_client = bigquery.Client(project=Config.GCP_PROJECT)

_CONNECTION_ID = (
    f"{Config.GCP_PROJECT}.{Config.GCP_LOCATION}.{Config.BIGLAKE_CONNECTION}"
)


def table_exists(namespace: str, table_name: str) -> bool:
    """Check if a BigQuery table already exists."""
    table_ref = f"{Config.GCP_PROJECT}.{namespace}.{table_name}"
    try:
        _client.get_table(table_ref)
        return True
    except Exception:
        return False


def evolve_schema(namespace: str, table_name: str, parquet_uri: str) -> list[str]:
    """Add columns from parquet that are missing in the target table.

    Bronze tables are append-only landing zones, so additive schema evolution
    is safe — new columns read as NULL from older Iceberg data files.

    Returns the list of column names that were added.
    """
    table_ref_str = f"{Config.GCP_PROJECT}.{namespace}.{table_name}"

    existing_table = _client.get_table(table_ref_str)
    existing_names = {field.name.lower() for field in existing_table.schema}

    # Infer incoming schema from parquet via temp external table
    temp_suffix = uuid.uuid4().hex[:8]
    temp_ref = f"`{Config.GCP_PROJECT}.{namespace}._schema_probe_{temp_suffix}`"
    _client.query(
        f"CREATE OR REPLACE EXTERNAL TABLE {temp_ref} "
        f"OPTIONS (format = 'PARQUET', uris = ['{parquet_uri}'])"
    ).result()

    try:
        temp_table = _client.get_table(
            f"{Config.GCP_PROJECT}.{namespace}._schema_probe_{temp_suffix}"
        )
        parquet_schema = list(temp_table.schema)
    finally:
        _client.query(f"DROP EXTERNAL TABLE IF EXISTS {temp_ref}").result()

    new_columns = [
        field for field in parquet_schema
        if field.name.lower() not in existing_names
    ]

    if not new_columns:
        return []

    added = []
    for field in new_columns:
        alter_sql = (
            f"ALTER TABLE `{table_ref_str}` "
            f"ADD COLUMN `{field.name}` {_to_sql_type(field.field_type)}"
        )
        _client.query(alter_sql).result()
        added.append(field.name)

    logger.info(
        "Schema evolution on %s.%s — added columns: %s",
        namespace,
        table_name,
        ", ".join(added),
    )
    return added


def create_iceberg_table(
    namespace: str,
    table_name: str,
    parquet_uri: str,
) -> str:
    """Create a new BigQuery Iceberg table and load initial data from parquet.

    Two-step approach:
    1. Create a temp external table to infer schema from the parquet file
    2. CREATE TABLE ... AS SELECT ... WITH CONNECTION ... OPTIONS(table_format='ICEBERG')

    BigQuery auto-registers the Iceberg table in the BigLake Metastore via
    the connection.

    Returns the BigQuery job ID as the load identifier.
    """
    storage_uri = f"{Config.ICEBERG_BASE_PATH}/{namespace}/{table_name}"
    table_ref = f"`{Config.GCP_PROJECT}.{namespace}.{table_name}`"
    connection_ref = f"`{_CONNECTION_ID}`"
    temp_suffix = uuid.uuid4().hex[:8]
    temp_table = f"`{Config.GCP_PROJECT}.{namespace}._temp_create_{temp_suffix}`"

    # Step 1: Create temp external table to infer schema from parquet
    create_temp_sql = f"""
    CREATE OR REPLACE EXTERNAL TABLE {temp_table}
    OPTIONS (
        format = 'PARQUET',
        uris = ['{parquet_uri}']
    )
    """
    _client.query(create_temp_sql).result()

    try:
        # Step 2: Create Iceberg table with data from temp table
        create_sql = f"""
        CREATE TABLE {table_ref}
        WITH CONNECTION {connection_ref}
        OPTIONS (
            file_format = 'PARQUET',
            table_format = 'ICEBERG',
            storage_uri = '{storage_uri}'
        )
        AS SELECT * FROM {temp_table}
        """
        job = _client.query(create_sql)
        job.result()
    finally:
        # Clean up temp table
        _client.query(f"DROP EXTERNAL TABLE IF EXISTS {temp_table}").result()

    load_id = job.job_id
    logger.info(
        "Created Iceberg table %s.%s — loaded from %s (job: %s)",
        namespace,
        table_name,
        parquet_uri,
        load_id,
    )
    return load_id


def load_data(
    namespace: str,
    table_name: str,
    parquet_uri: str,
    write_mode: str,
) -> str:
    """Load parquet data into an existing BigQuery Iceberg table.

    Uses INSERT INTO ... SELECT with SAFE_CAST to handle type mismatches
    between the agent's parquet output and the target table schema.

    write_mode: APPEND or OVERWRITE.
    Returns the BigQuery job ID as the load identifier.
    """
    evolve_schema(namespace, table_name, parquet_uri)

    table_ref_str = f"{Config.GCP_PROJECT}.{namespace}.{table_name}"
    table_ref = f"`{table_ref_str}`"
    temp_suffix = uuid.uuid4().hex[:8]
    temp_table = f"`{Config.GCP_PROJECT}.{namespace}._temp_load_{temp_suffix}`"

    # Create temp external table from parquet
    _client.query(
        f"CREATE OR REPLACE EXTERNAL TABLE {temp_table} "
        f"OPTIONS (format = 'PARQUET', uris = ['{parquet_uri}'])"
    ).result()

    try:
        select_clause = _build_cast_select(
            namespace, table_name,
            f"{Config.GCP_PROJECT}.{namespace}._temp_load_{temp_suffix}",
        )

        if write_mode == "OVERWRITE":
            _client.query(f"DELETE FROM {table_ref} WHERE TRUE").result()

        insert_sql = f"INSERT INTO {table_ref} SELECT {select_clause} FROM {temp_table}"
        job = _client.query(insert_sql)
        job.result()
    finally:
        _client.query(f"DROP EXTERNAL TABLE IF EXISTS {temp_table}").result()

    load_id = job.job_id
    logger.info(
        "%s %s.%s — loaded from %s (job: %s)",
        write_mode,
        namespace,
        table_name,
        parquet_uri,
        load_id,
    )
    return load_id


# BigQuery Python client field_type → BigQuery SQL type
_BQ_TYPE_MAP = {
    "INTEGER": "INT64",
    "FLOAT": "FLOAT64",
    "BOOLEAN": "BOOL",
    "STRING": "STRING",
    "TIMESTAMP": "TIMESTAMP",
    "DATE": "DATE",
    "DATETIME": "DATETIME",
    "TIME": "TIME",
    "NUMERIC": "NUMERIC",
    "BIGNUMERIC": "BIGNUMERIC",
    "BYTES": "BYTES",
    "GEOGRAPHY": "GEOGRAPHY",
    "JSON": "JSON",
}


def _to_sql_type(field_type: str) -> str:
    """Convert BigQuery Python client field_type to SQL type name."""
    return _BQ_TYPE_MAP.get(field_type, field_type)


def _build_cast_select(
    namespace: str,
    table_name: str,
    temp_table_name: str,
) -> str:
    """Build a SELECT clause with SAFE_CAST for type mismatches.

    Compares the temp (source) table schema against the target table schema
    and generates SAFE_CAST expressions where types differ.
    """
    table_ref_str = f"{Config.GCP_PROJECT}.{namespace}.{table_name}"
    target_table = _client.get_table(table_ref_str)
    target_fields = {f.name.lower(): f for f in target_table.schema}

    temp_meta = _client.get_table(temp_table_name)
    source_fields = {f.name.lower(): f for f in temp_meta.schema}

    select_cols = []
    for name_lower, field in target_fields.items():
        if name_lower in source_fields:
            src_type = _to_sql_type(source_fields[name_lower].field_type)
            tgt_type = _to_sql_type(field.field_type)
            if src_type != tgt_type:
                select_cols.append(
                    f"SAFE_CAST(`{field.name}` AS {tgt_type}) AS `{field.name}`"
                )
            else:
                select_cols.append(f"`{field.name}`")
        else:
            select_cols.append(f"NULL AS `{field.name}`")

    # Include extra columns from source not in target (added by evolve_schema)
    for name_lower, field in source_fields.items():
        if name_lower not in target_fields:
            select_cols.append(f"`{field.name}`")

    return ", ".join(select_cols)


def upsert_data(
    namespace: str,
    table_name: str,
    parquet_uri: str,
    upsert_keys: list[str],
) -> str:
    """MERGE new parquet data into an existing Iceberg table using upsert keys.

    Creates a temp external table from the parquet, deletes matching rows
    by key from the target, then appends new data with SAFE_CAST for type
    mismatches.

    Returns the BigQuery job ID as the load identifier.
    """
    evolve_schema(namespace, table_name, parquet_uri)

    table_ref = f"`{Config.GCP_PROJECT}.{namespace}.{table_name}`"
    temp_suffix = uuid.uuid4().hex[:8]
    temp_fqn = f"{Config.GCP_PROJECT}.{namespace}._temp_upsert_{temp_suffix}"
    temp_table = f"`{temp_fqn}`"

    _client.query(
        f"CREATE OR REPLACE EXTERNAL TABLE {temp_table} "
        f"OPTIONS (format = 'PARQUET', uris = ['{parquet_uri}'])"
    ).result()

    try:
        # Delete rows in target that match incoming upsert keys
        join_condition = " AND ".join(
            f"target.{key} = source.{key}" for key in upsert_keys
        )

        delete_sql = f"""
        DELETE FROM {table_ref} AS target
        WHERE EXISTS (
            SELECT 1 FROM {temp_table} AS source
            WHERE {join_condition}
        )
        """
        _client.query(delete_sql).result()

        # Append new data with type casting
        select_clause = _build_cast_select(namespace, table_name, temp_fqn)
        insert_sql = f"INSERT INTO {table_ref} SELECT {select_clause} FROM {temp_table}"
        job = _client.query(insert_sql)
        job.result()
    finally:
        _client.query(f"DROP EXTERNAL TABLE IF EXISTS {temp_table}").result()

    load_id = job.job_id
    logger.info(
        "UPSERT %s.%s — loaded from %s (job: %s)",
        namespace,
        table_name,
        parquet_uri,
        load_id,
    )
    return load_id
