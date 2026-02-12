"""Custom tools for the Data Insights Agent."""

from typing import Any
from google.cloud import bigquery
from .config import settings


"""Global cache for BigQuery table schema information.

This cache stores table metadata to reduce API calls to BigQuery and improve
response times for repeated schema lookups. The cache is populated on-demand
when tables are accessed via get_available_tables() or get_table_schema().

Schema cache structure:
    {
        "project.dataset.table_name": {
            "name": str,
            "full_name": str,
            "description": str,
            "num_rows": int,
            "columns": [{"name": str, "type": str, "description": str, "mode": str}]
        }
    }

WARNING - Thread Safety:
    This is a module-level mutable dictionary. It is NOT thread-safe.
    Concurrent requests may cause race conditions. For production use with
    concurrent workers, consider using a thread-safe cache implementation
    (e.g., threading.Lock) or external cache (Redis, Memcached).

Cache Management:
    - Cache never expires automatically
    - Use clear_schema_cache() to manually clear if table structures change
    - Cache is lost on server restart (in-memory only)
"""
_schema_cache: dict[str, dict] = {}

"""Pending insights reported by the agent via the report_insight tool.

Insights are accumulated here during a single agent invocation and then
drained by the API route after the event stream completes. This replaces
the previous regex-based approach, which required the agent to use exact
magic phrases (e.g. "I notice that ...") that were fragile and hard to scale.

WARNING - Thread Safety and Session Isolation:
    Same caveats as _last_query_result below. This list is module-level and
    NOT thread-safe or session-aware. For production with concurrent users,
    store pending insights in session-scoped state instead of a global list.

Lifecycle:
    - Populated by report_insight() tool calls during agent execution
    - Drained (read + cleared) by get_and_clear_pending_insights() in routes.py
      after the ADK event stream finishes
"""
_pending_insights: list[dict[str, str]] = []


"""Global storage for the most recent query result.

This variable stores the last successful query result from execute_query_with_metadata()
to enable subsequent enrichment and calculation operations without re-querying the
database. It is used by apply_enrichment() and add_calculated_column() to merge
additional data into existing results.

Structure matches the return format of execute_query_with_metadata():
    {
        "status": "success",
        "columns": [{"name": str, "type": str, "is_enriched": bool, "is_calculated": bool}],
        "rows": [dict[str, Any]],
        "total_rows": int,
        "query_time_ms": float,
        "sql": str,
        "enrichment_metadata": dict (optional),
        "calculation_metadata": dict (optional)
    }

WARNING - Thread Safety and Session Isolation:
    This is a module-level global variable. It is NOT thread-safe and NOT session-aware.

    Problems in concurrent environments:
    - Multiple concurrent requests will overwrite each other's query results
    - User A's enrichment may accidentally apply to User B's query
    - Race conditions can cause data corruption

    Current Limitation:
    This implementation assumes single-threaded or low-concurrency usage.
    For production with multiple concurrent users, refactor to use:
    - Session-scoped storage (SessionService)
    - Thread-local storage (threading.local())
    - Request context (e.g., FastAPI Request state)

SIDE EFFECT WARNING:
    execute_query_with_metadata() ALWAYS updates this variable on successful query.
    This is intentional to support the enrichment workflow but may be surprising.
    See execute_query_with_metadata() docstring for details.
"""
_last_query_result: dict[str, Any] | None = None


def get_available_tables() -> dict[str, Any]:
    """Get a list of all available tables in the configured BigQuery dataset.

    Retrieves metadata for all tables in the BigQuery dataset specified in settings,
    including table descriptions and column schemas. Results are cached in the global
    _schema_cache to improve performance on repeated calls.

    This tool is typically called by the AI agent when a user asks questions like:
    - "What data is available?"
    - "Show me all tables"
    - "What can I query?"

    Returns:
        dict[str, Any]: A dictionary with the following structure:
            {
                "status": "success" | "error",
                "dataset": str,  # The dataset name (only on success)
                "tables": [      # List of table metadata (only on success)
                    {
                        "name": str,              # Table name (e.g., "sales_data")
                        "full_name": str,         # Fully qualified ID (e.g., "project.dataset.sales_data")
                        "description": str,       # Table description (empty string if none)
                        "num_rows": int,          # Row count
                        "columns": [
                            {
                                "name": str,        # Column name
                                "type": str,        # BigQuery type (e.g., "STRING", "INTEGER")
                                "description": str, # Column description (empty if none)
                                "mode": str         # "REQUIRED", "NULLABLE", or "REPEATED"
                            }
                        ]
                    }
                ],
                "error": str  # Error message (only on error)
            }

    Raises:
        Does not raise exceptions. Errors are returned in the response dict with
        status="error" and an error message.

    Side Effects:
        - Populates the global _schema_cache with table metadata for future lookups
        - Makes API calls to BigQuery (unless data is already cached)

    Examples:
        >>> result = get_available_tables()
        >>> if result["status"] == "success":
        ...     for table in result["tables"]:
        ...         print(f"{table['name']}: {table['num_rows']} rows")
        sales_data: 10523 rows
        customer_info: 2891 rows

        >>> # Error case
        >>> result = get_available_tables()  # If BigQuery fails
        >>> result
        {
            "status": "error",
            "error": "403 Forbidden: Access Denied: Dataset project:dataset: ..."
        }

    Notes:
        - Caching behavior: First call queries BigQuery API; subsequent calls use cache
        - Cache persistence: In-memory only, lost on server restart
        - Cache invalidation: Use clear_schema_cache() if table structure changes
    """
    try:
        client = bigquery.Client(project=settings.google_cloud_project)
        dataset_ref = f"{settings.google_cloud_project}.{settings.bigquery_dataset}"

        tables = list(client.list_tables(dataset_ref))
        table_info = []

        for table in tables:
            full_table_id = f"{dataset_ref}.{table.table_id}"

            # Check cache first
            if full_table_id in _schema_cache:
                table_info.append(_schema_cache[full_table_id])
                continue

            # Get detailed table info
            table_ref = client.get_table(full_table_id)
            columns = [
                {
                    "name": field.name,
                    "type": field.field_type,
                    "description": field.description or "",
                    "mode": field.mode
                }
                for field in table_ref.schema
            ]

            info = {
                "name": table.table_id,
                "full_name": full_table_id,
                "description": table_ref.description or "",
                "num_rows": table_ref.num_rows,
                "columns": columns
            }

            # Cache the result
            _schema_cache[full_table_id] = info
            table_info.append(info)

        return {
            "status": "success",
            "dataset": settings.bigquery_dataset,
            "tables": table_info
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_table_schema(table_name: str) -> dict[str, Any]:
    """
    Get detailed schema information for a specific table.

    Args:
        table_name: The name of the table (can be just the table name or fully qualified)

    Returns:
        dict: A dictionary containing:
            - status: "success" or "error"
            - table_name: The table name
            - columns: List of column details
            - sample_values: Sample values for each column (for context)
    """
    try:
        client = bigquery.Client(project=settings.google_cloud_project)

        # Handle both simple and fully qualified table names
        if "." not in table_name:
            full_table_id = f"{settings.google_cloud_project}.{settings.bigquery_dataset}.{table_name}"
        else:
            full_table_id = table_name

        table_ref = client.get_table(full_table_id)

        columns = []
        for field in table_ref.schema:
            col_info = {
                "name": field.name,
                "type": field.field_type,
                "description": field.description or "",
                "mode": field.mode,
                "is_nullable": field.mode != "REQUIRED"
            }
            columns.append(col_info)

        # Get sample values for context (limited query)
        sample_query = f"SELECT * FROM `{full_table_id}` LIMIT 5"
        sample_results = client.query(sample_query).result()
        sample_rows = [dict(row) for row in sample_results]

        return {
            "status": "success",
            "table_name": table_name,
            "full_table_id": full_table_id,
            "description": table_ref.description or "",
            "num_rows": table_ref.num_rows,
            "columns": columns,
            "sample_rows": sample_rows
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def validate_sql_query(sql: str) -> dict[str, Any]:
    """Validate a SQL query without executing it using BigQuery's dry run.

    Performs a dry run validation of the SQL query to check for syntax errors,
    permission issues, and table/column existence. Also provides cost estimation
    by calculating the amount of data that would be processed. This prevents
    expensive or failing queries from being executed.

    This tool is typically called by the AI agent before execute_query_with_metadata()
    to ensure the generated SQL is correct.

    Args:
        sql (str): The SQL query to validate. Should be a complete SELECT statement
            or other valid BigQuery SQL. Can include comments, newlines, and
            multiple clauses.

    Returns:
        dict[str, Any]: Validation result with the following structure:

            On success (valid query):
            {
                "status": "valid",
                "estimated_bytes": int,     # Raw byte count (e.g., 1048576)
                "estimated_size": str,      # Human-readable size (e.g., "1.00 MB")
                "message": str              # Confirmation message with size
            }

            On failure (invalid query):
            {
                "status": "invalid",
                "error": str  # Error message from BigQuery (e.g., syntax error, missing table)
            }

    Raises:
        Does not raise exceptions. All errors are captured and returned in the
        response dict with status="invalid".

    Side Effects:
        - Makes API call to BigQuery (dry_run=True, so no data is processed)
        - No caching or global state modifications

    Examples:
        >>> # Valid query
        >>> result = validate_sql_query("SELECT * FROM `project.dataset.table` LIMIT 10")
        >>> result
        {
            "status": "valid",
            "estimated_bytes": 524288,
            "estimated_size": "512.00 KB",
            "message": "Query is valid. Estimated data to process: 512.00 KB"
        }

        >>> # Invalid query - syntax error
        >>> result = validate_sql_query("SELECT * FROM")
        >>> result
        {
            "status": "invalid",
            "error": "Syntax error: Expected keyword FROM but got end of statement"
        }

        >>> # Invalid query - table not found
        >>> result = validate_sql_query("SELECT * FROM `project.dataset.nonexistent`")
        >>> result
        {
            "status": "invalid",
            "error": "Not found: Table project:dataset.nonexistent"
        }

        >>> # Large query warning
        >>> result = validate_sql_query("SELECT * FROM `huge_table`")
        >>> result
        {
            "status": "valid",
            "estimated_bytes": 5368709120,
            "estimated_size": "5.00 GB",
            "message": "Query is valid. Estimated data to process: 5.00 GB"
        }

    Notes:
        - Dry run does not consume query quota or cost money
        - Estimated bytes can help identify expensive queries before execution
        - Use this before execute_query_with_metadata() for safety
    """
    try:
        client = bigquery.Client(project=settings.google_cloud_project)

        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        query_job = client.query(sql, job_config=job_config)

        # Convert bytes to human-readable format
        bytes_processed = query_job.total_bytes_processed
        if bytes_processed < 1024:
            size_str = f"{bytes_processed} B"
        elif bytes_processed < 1024 * 1024:
            size_str = f"{bytes_processed / 1024:.2f} KB"
        elif bytes_processed < 1024 * 1024 * 1024:
            size_str = f"{bytes_processed / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{bytes_processed / (1024 * 1024 * 1024):.2f} GB"

        return {
            "status": "valid",
            "estimated_bytes": bytes_processed,
            "estimated_size": size_str,
            "message": f"Query is valid. Estimated data to process: {size_str}"
        }
    except Exception as e:
        return {
            "status": "invalid",
            "error": str(e)
        }


def execute_query_with_metadata(sql: str, max_rows: int = 1000) -> dict[str, Any]:
    """Execute a SQL query and return results with metadata for the frontend.

    Runs the provided SQL query against BigQuery and returns the results in a
    structured format suitable for display in the frontend. Automatically adds
    a LIMIT clause if not present to prevent accidentally returning huge datasets.

    **CRITICAL SIDE EFFECT**: This function ALWAYS updates the global variable
    _last_query_result with a copy of the successful result. This enables the
    enrichment and calculation workflow (apply_enrichment and add_calculated_column)
    to operate on the query results without re-executing the query.

    This tool is the primary data retrieval function used by the AI agent to
    answer user questions that require querying the database.

    Args:
        sql (str): The SQL query to execute. Should be a valid BigQuery SQL
            SELECT statement. If the query doesn't contain a LIMIT clause and
            max_rows is specified, a LIMIT will be automatically appended.
        max_rows (int, optional): Maximum number of rows to return. Defaults to 1000.
            Set to None or 0 to disable the automatic LIMIT (use with caution).
            If the query already has a LIMIT clause, this parameter is ignored.

    Returns:
        dict[str, Any]: Query result with the following structure:

            On success:
            {
                "status": "success",
                "columns": [
                    {
                        "name": str,    # Column name
                        "type": str     # BigQuery type (STRING, INTEGER, FLOAT64, etc.)
                    }
                ],
                "rows": [
                    {column_name: value, ...}  # Each row as a dict
                ],
                "total_rows": int,      # Number of rows returned (may be less than query total)
                "query_time_ms": float, # Query execution time in milliseconds
                "sql": str              # The actual SQL executed (with LIMIT if added)
            }

            On error:
            {
                "status": "error",
                "error": str,  # Error message from BigQuery
                "sql": str     # The SQL that failed
            }

    Raises:
        Does not raise exceptions. All errors are captured and returned in the
        response dict with status="error".

    Side Effects:
        **WARNING - Global State Mutation**:
        - Updates the global _last_query_result variable with a copy of the result
        - This happens on EVERY successful query execution
        - NOT thread-safe: Concurrent requests will overwrite each other's results
        - NOT session-aware: User A's query may be overwritten by User B's query

        Other side effects:
        - Executes the query on BigQuery (consumes quota and may incur costs)
        - No caching of results

    Examples:
        >>> # Simple query
        >>> result = execute_query_with_metadata(
        ...     "SELECT state, COUNT(*) as count FROM `project.dataset.sales` GROUP BY state"
        ... )
        >>> result
        {
            "status": "success",
            "columns": [{"name": "state", "type": "STRING"}, {"name": "count", "type": "INTEGER"}],
            "rows": [
                {"state": "CA", "count": 150},
                {"state": "NY", "count": 89},
                {"state": "TX", "count": 203}
            ],
            "total_rows": 3,
            "query_time_ms": 234.56,
            "sql": "SELECT state, COUNT(*) as count FROM `project.dataset.sales` GROUP BY state LIMIT 1000"
        }

        >>> # Query with custom row limit
        >>> result = execute_query_with_metadata(
        ...     "SELECT * FROM `project.dataset.customers`",
        ...     max_rows=10
        ... )
        >>> result["total_rows"]
        10

        >>> # Query error
        >>> result = execute_query_with_metadata("SELECT * FROM nonexistent_table")
        >>> result
        {
            "status": "error",
            "error": "Not found: Table project:dataset.nonexistent_table",
            "sql": "SELECT * FROM nonexistent_table LIMIT 1000"
        }

        >>> # After this function, _last_query_result is set for enrichment:
        >>> execute_query_with_metadata("SELECT state FROM sales")
        >>> # Now apply_enrichment() can add data to this result
        >>> apply_enrichment("state", [...])  # Merges into _last_query_result

    Notes:
        - Always use validate_sql_query() first to catch errors early
        - Date/time values are converted to ISO format strings
        - Bytes values are decoded to UTF-8 strings
        - Result is stored in _last_query_result for enrichment/calculation workflows
        - In production with concurrent users, consider session-scoped result storage
    """
    global _last_query_result

    try:
        client = bigquery.Client(project=settings.google_cloud_project)

        # Add LIMIT if not present and max_rows is specified
        sql_lower = sql.lower().strip()
        if "limit" not in sql_lower and max_rows:
            sql = f"{sql.rstrip(';')} LIMIT {max_rows}"

        import time
        start_time = time.time()
        query_job = client.query(sql)
        results = query_job.result()
        end_time = time.time()

        # Extract column information
        columns = [
            {
                "name": field.name,
                "type": field.field_type
            }
            for field in results.schema
        ]

        # Convert rows to list of dicts, handling special types
        rows = []
        for row in results:
            row_dict = {}
            for key, value in row.items():
                # Convert non-serializable types to strings
                if hasattr(value, 'isoformat'):
                    row_dict[key] = value.isoformat()
                elif isinstance(value, bytes):
                    row_dict[key] = value.decode('utf-8', errors='replace')
                else:
                    row_dict[key] = value
            rows.append(row_dict)

        result = {
            "status": "success",
            "columns": columns,
            "rows": rows,
            "total_rows": len(rows),
            "query_time_ms": round((end_time - start_time) * 1000, 2),
            "sql": sql
        }

        # Store for potential enrichment
        _last_query_result = result.copy()

        return result
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "sql": sql
        }


def clear_schema_cache() -> dict[str, str]:
    """
    Clear the cached schema information. Useful when table structures change.

    Returns:
        dict: Status message
    """
    global _schema_cache
    count = len(_schema_cache)
    _schema_cache = {}
    return {
        "status": "success",
        "message": f"Cleared {count} cached table schemas"
    }


def apply_enrichment(
    source_column: str,
    enrichment_data: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply enrichment data to the last query result using a 5-step merge process.

    This function merges externally-sourced enrichment data (from Google Search via
    the enrichment sub-agent) into the query results stored in _last_query_result.
    It adds new columns prefixed with "_enriched_" containing structured metadata
    (value, source, confidence, freshness, warnings).

    **WORKFLOW**: This is Step 2 of the enrichment process:
    1. Main agent calls execute_query_with_metadata() → stores result in _last_query_result
    2. Main agent calls request_enrichment() → validates and transfers to enrichment_agent
    3. Enrichment agent searches Google and returns structured enrichment_data
    4. **THIS FUNCTION**: Merges enrichment_data into _last_query_result
    5. Frontend displays enriched columns with metadata badges

    **GUARDRAILS** (enforced upstream in request_enrichment):
    - Maximum 20 unique values can be enriched per request
    - Maximum 5 fields can be added per value
    - All enriched data MUST include source attribution

    Args:
        source_column (str): The column name that was enriched (must exist in _last_query_result).
            Examples: "state", "city", "company_name", "hotel_name"
        enrichment_data (list[dict[str, Any]]): List of enrichment objects from enrichment_agent.
            Each object must have:
            - original_value (str): The value that was enriched (e.g., "CA", "Texas")
            - enriched_fields (dict): Mapping of field_name to enriched metadata:
                {
                    "field_name": {
                        "value": Any,              # The enriched value
                        "source": str,             # Data source (e.g., "Wikipedia", "US Census")
                        "confidence": str,         # "high", "medium", or "low"
                        "freshness": str,          # "static", "current", "dated", or "stale"
                        "warning": str | None      # Optional warning about data quality
                    }
                }

    Returns:
        dict[str, Any]: Updated query result with enriched columns added, or error dict.

            On success:
            {
                "status": "success",
                "columns": [..., {"name": "_enriched_capital", "type": "STRING", "is_enriched": True}],
                "rows": [
                    {
                        "state": "CA",
                        "_enriched_capital": {
                            "value": "Sacramento",
                            "source": "Wikipedia",
                            "confidence": "high",
                            "freshness": "static",
                            "warning": null
                        }
                    }
                ],
                "enrichment_metadata": {
                    "source_column": "state",
                    "enriched_fields": ["capital", "population"],
                    "total_enriched": 3,
                    "warnings": ["No enrichment data found for 'PR'"],
                    "partial_failure": true
                }
            }

            On error:
            {
                "status": "error",
                "error": "No query result available to enrich. Run a query first."
            }

    Raises:
        Does not raise exceptions. Errors are returned in the response dict.

    Side Effects:
        - Updates the global _last_query_result with enriched data
        - This allows add_calculated_column() to reference enriched fields
        - NOT thread-safe (see _last_query_result global variable documentation)

    Examples:
        >>> # First, execute a query
        >>> execute_query_with_metadata("SELECT state FROM sales GROUP BY state")

        >>> # Then apply enrichment from the enrichment agent
        >>> enrichment = [
        ...     {
        ...         "original_value": "CA",
        ...         "enriched_fields": {
        ...             "capital": {"value": "Sacramento", "source": "Google", "confidence": "high", "freshness": "static"},
        ...             "population": {"value": "39.5M", "source": "Census", "confidence": "medium", "freshness": "current"}
        ...         }
        ...     },
        ...     {
        ...         "original_value": "TX",
        ...         "enriched_fields": {
        ...             "capital": {"value": "Austin", "source": "Wikipedia", "confidence": "high", "freshness": "static"},
        ...             "population": {"value": "29.1M", "source": "Census", "confidence": "medium", "freshness": "current"}
        ...         }
        ...     }
        ... ]
        >>> result = apply_enrichment("state", enrichment)
        >>> result["columns"]
        [{"name": "state", "type": "STRING"},
         {"name": "_enriched_capital", "type": "STRING", "is_enriched": True},
         {"name": "_enriched_population", "type": "STRING", "is_enriched": True}]

        >>> # Error case: No prior query
        >>> apply_enrichment("state", enrichment)
        {"status": "error", "error": "No query result available to enrich. Run a query first."}

    Notes:
        - Enriched columns are prefixed with "_enriched_" to distinguish them from original data
        - Idempotent: Calling twice with same data won't duplicate columns
        - Partial failures are tracked: Some values may fail enrichment while others succeed
        - Frontend displays enriched values with source badges and confidence indicators
        - Enriched columns can be used in add_calculated_column() expressions
    """
    global _last_query_result

    if _last_query_result is None:
        return {
            "status": "error",
            "error": "No query result available to enrich. Run a query first."
        }

    if not enrichment_data:
        return {
            "status": "error",
            "error": "No enrichment data provided."
        }

    # ========== STEP 1: Initialize and Validate ==========
    # Create a deep copy to avoid mutating the original result during merge
    import copy
    result = copy.deepcopy(_last_query_result)

    # Track existing columns to prevent duplicate enrichment columns
    existing_columns = {col["name"] for col in result.get("columns", [])}

    # ========== STEP 2: Build Enrichment Lookup Map ==========
    # Convert enrichment_data list into a fast lookup dictionary
    # Key: original_value (e.g., "CA"), Value: enriched_fields dict
    enrichment_map = {}
    enriched_field_names = set()

    for item in enrichment_data:
        original_value = item.get("original_value", "")
        enriched_fields = item.get("enriched_fields", {})
        enrichment_map[original_value] = enriched_fields
        # Collect all field names across all enrichments (e.g., "capital", "population")
        enriched_field_names.update(enriched_fields.keys())

    # ========== STEP 3: Add Enriched Columns to Schema ==========
    # Add new column metadata for each enriched field (with _enriched_ prefix)
    # Only add if column doesn't already exist (idempotency)
    for field_name in sorted(enriched_field_names):
        col_name = f"_enriched_{field_name}"
        if col_name not in existing_columns:
            result["columns"].append({
                "name": col_name,
                "type": "STRING",  # All enriched values stored as strings with metadata
                "is_enriched": True  # Flag for frontend to apply special rendering
            })

    # ========== STEP 4: Merge Enriched Data into Rows ==========
    # For each row, look up enrichment by source column value and add enriched fields
    warnings = []
    for row in result.get("rows", []):
        # Get the value from the source column (e.g., row["state"] = "CA")
        source_value = str(row.get(source_column, ""))
        # Look up enrichment for this specific value
        enrichment = enrichment_map.get(source_value)

        if enrichment:
            # Enrichment found: Add each enriched field to the row
            for field_name in enriched_field_names:
                col_name = f"_enriched_{field_name}"
                # Skip if this cell already has valid enriched data (idempotency)
                existing_value = row.get(col_name)
                if isinstance(existing_value, dict) and existing_value.get("value") is not None:
                    continue

                field_data = enrichment.get(field_name)
                if field_data:
                    # Add enriched value with full metadata
                    row[col_name] = {
                        "value": field_data.get("value"),
                        "source": field_data.get("source"),
                        "confidence": field_data.get("confidence", "medium"),
                        "freshness": field_data.get("freshness", "current"),
                        "warning": field_data.get("warning")
                    }
                else:
                    # Field was requested but not found in enrichment response
                    row[col_name] = {
                        "value": None,
                        "source": None,
                        "confidence": None,
                        "freshness": None,
                        "warning": "Field not found in enrichment"
                    }
        else:
            # No enrichment found for this row's source value
            # Add null placeholders with warnings for all enriched fields
            for field_name in enriched_field_names:
                col_name = f"_enriched_{field_name}"
                # Skip if already has data (idempotency)
                if col_name in row and isinstance(row[col_name], dict) and row[col_name].get("value") is not None:
                    continue
                row[col_name] = {
                    "value": None,
                    "source": None,
                    "confidence": None,
                    "freshness": None,
                    "warning": f"No enrichment data found for '{source_value}'"
                }
            # Track missing enrichments for metadata (deduplicate warnings)
            if source_value and source_value not in [w.split("'")[1] for w in warnings if "'" in w]:
                warnings.append(f"No enrichment data found for '{source_value}'")

    # ========== STEP 5: Add Enrichment Metadata ==========
    # Attach metadata about the enrichment operation for frontend display and debugging
    result["enrichment_metadata"] = {
        "source_column": source_column,  # Which column was enriched
        "enriched_fields": list(enriched_field_names),  # Which fields were added
        "total_enriched": len(enrichment_map),  # How many values were successfully enriched
        "warnings": warnings[:5],  # Limit to first 5 warnings to avoid response bloat
        "partial_failure": len(warnings) > 0  # Flag if any enrichments failed
    }

    # Update the stored result so add_calculated_column can use enriched data
    _last_query_result = result

    return result


def add_calculated_column(
    column_name: str,
    expression: str,
    format_type: str = "number"
) -> dict[str, Any]:
    """Add a calculated column to query results using safe expression evaluation.

    Adds a derived column to _last_query_result by evaluating a mathematical expression
    on existing column values. Uses Python's eval() with restricted namespace for safety.
    Automatically extracts values from enriched columns (which are stored as metadata dicts).

    This enables users to perform calculations on query results without re-running the
    database query, which is especially useful for combining base data with enriched data.

    **EXPRESSION EVALUATION SECURITY**:
    - Uses eval() with restricted __builtins__ (no access to os, sys, imports, etc.)
    - Only allows mathematical operators: +, -, *, /, %, **
    - Column names are validated against available columns before evaluation
    - No function calls or attribute access allowed (except built-in math)

    **AUTOMATIC VALUE EXTRACTION**:
    - Normal columns: Used directly as numbers
    - Enriched columns: Automatically extracts the 'value' field from metadata dict
    - String values: Attempts to parse numbers (e.g., "39.5 million" → 39.5)
    - None values: Converted to 0 for calculation (prevents errors)

    Args:
        column_name (str): Name for the new calculated column.
            Examples: "residents_per_store", "profit_margin", "growth_rate"
        expression (str): Mathematical expression using existing column names.
            Supported operators: +, -, *, /, %, ** (power)
            For enriched columns, use the _enriched_ prefix (e.g., "_enriched_population")
            The function automatically extracts .value from enriched column objects.

            Valid expression examples:
            - "population / store_count"
            - "revenue - costs"
            - "(new_customers / total_customers) * 100"
            - "_enriched_population / store_count"
            - "sales ** 2"  # Squared

        format_type (str, optional): How to format the calculated values. Defaults to "number".
            Options:
            - "number": General numeric format (auto rounds to 2 decimals or integer)
            - "integer": Rounds to whole numbers
            - "percent": Rounds to 2 decimal places (for display as percentages)
            - "currency": Rounds to 2 decimal places (for currency display)

    Returns:
        dict[str, Any]: Updated query result with calculated column added, or error dict.

            On success:
            {
                "status": "success",
                "columns": [..., {"name": "residents_per_store", "type": "FLOAT64", "is_calculated": True}],
                "rows": [
                    {
                        "state": "CA",
                        "population": 39500000,
                        "store_count": 100,
                        "residents_per_store": {
                            "value": 395000.0,
                            "expression": "population / store_count",
                            "format_type": "number",
                            "is_calculated": True
                        }
                    }
                ],
                "calculation_metadata": {
                    "calculated_columns": [
                        {"name": "residents_per_store", "expression": "population / store_count", "format_type": "number"}
                    ],
                    "warnings": []
                }
            }

            On error:
            {
                "status": "error",
                "error": "No query result available. Run a query first."
            }

            Or:
            {
                "status": "error",
                "error": "Column(s) not found: invalid_column. Available columns: state, population, store_count"
            }

    Raises:
        Does not raise exceptions. All errors are captured and returned in the response
        dict or stored in row-level warnings.

    Side Effects:
        - Updates the global _last_query_result with the calculated column
        - Allows chaining multiple calculated columns
        - NOT thread-safe (see _last_query_result global variable documentation)

    Examples:
        >>> # Simple calculation on base columns
        >>> execute_query_with_metadata("SELECT state, population, store_count FROM data")
        >>> result = add_calculated_column("residents_per_store", "population / store_count")
        >>> result["rows"][0]["residents_per_store"]
        {"value": 395000.0, "expression": "population / store_count", "format_type": "number", "is_calculated": True}

        >>> # Using enriched data
        >>> apply_enrichment("state", [...])  # Adds _enriched_gdp column
        >>> result = add_calculated_column("gdp_per_capita", "_enriched_gdp / population", "currency")
        >>> result["rows"][0]["gdp_per_capita"]
        {"value": 75000.25, "format_type": "currency", ...}

        >>> # Complex expression
        >>> result = add_calculated_column(
        ...     "market_share",
        ...     "(our_sales / total_market_sales) * 100",
        ...     "percent"
        ... )

        >>> # Error: Division by zero
        >>> result = add_calculated_column("invalid", "revenue / 0")
        >>> result["rows"][0]["invalid"]["warning"]
        "Division by zero"

        >>> # Error: Missing column
        >>> result = add_calculated_column("bad", "nonexistent_col * 2")
        >>> result
        {"status": "error", "error": "Column(s) not found: nonexistent_col. Available columns: ..."}

    Notes:
        - Idempotent: Calling twice with same column_name returns current result (no duplicate)
        - Per-row error handling: Failed calculations store None with warning in that row
        - String parsing: "39.5 million" extracts 39.5, ignoring text after first number
        - Enriched column auto-extraction: _enriched_population.value used automatically
        - Format types are hints for frontend display, actual values stored as numbers
        - Warnings limited to first 5 rows to prevent response bloat
    """
    global _last_query_result

    if _last_query_result is None:
        return {
            "status": "error",
            "error": "No query result available. Run a query first."
        }

    import copy
    import re
    result = copy.deepcopy(_last_query_result)

    # ========== Validation Phase ==========
    # Get available column names for validation
    available_columns = {col["name"] for col in result["columns"]}

    # Check if this calculated column already exists (idempotency)
    if column_name in available_columns:
        # Already exists, return the current result without modification
        return result

    # ========== Expression Parsing Phase ==========
    # Parse expression to find column references using regex
    # Match word characters that could be column names (including _enriched_ prefix)
    # Example: "population / store_count" → {"population", "store_count"}
    # Example: "_enriched_gdp * 1000" → {"_enriched_gdp"}
    potential_columns = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expression))

    # Filter to only actual columns (exclude Python keywords and functions)
    # This prevents "True", "False", "None" from being treated as column names
    excluded = {'and', 'or', 'not', 'if', 'else', 'True', 'False', 'None', 'in', 'is'}
    referenced_columns = potential_columns - excluded

    # Check all referenced columns exist before attempting calculation
    missing_columns = referenced_columns - available_columns
    if missing_columns:
        return {
            "status": "error",
            "error": f"Column(s) not found: {', '.join(missing_columns)}. "
                     f"Available columns: {', '.join(sorted(available_columns))}"
        }

    # ========== Schema Update Phase ==========
    # Add the new column to schema metadata
    result["columns"].append({
        "name": column_name,
        "type": "FLOAT64" if format_type != "integer" else "INTEGER",
        "is_calculated": True  # Flag for frontend to apply special rendering
    })

    # ========== Calculation Phase ==========
    # Calculate values for each row using safe eval()
    errors = []
    for i, row in enumerate(result.get("rows", [])):
        try:
            # Build a context dict for eval with column values
            # This creates a safe namespace containing only the column values
            context = {}
            for col in referenced_columns:
                value = row.get(col)

                # STEP 1: Extract value from enriched columns
                # Enriched columns are stored as dicts with metadata
                # Example: {"value": 39.5, "source": "Census", "confidence": "high", ...}
                # We only need the numeric .value field for calculation
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]

                # STEP 2: Convert value to float for mathematical operations
                if value is None:
                    # Treat None as 0 to prevent calculation errors
                    # Alternative: Could skip rows with None values
                    context[col] = 0
                elif isinstance(value, str):
                    # STEP 3: Parse numbers from string values
                    # Example: "39.5 million" → extract "39.5", ignore " million"
                    # Regex removes all non-digit, non-decimal characters
                    clean_val = re.sub(r'[^\d.]+', '', value.split()[0] if value else '0')
                    try:
                        context[col] = float(clean_val) if clean_val else 0
                    except ValueError:
                        context[col] = 0
                else:
                    # Normal numeric value (int, float)
                    context[col] = float(value)

            # STEP 4: Safely evaluate the expression using restricted eval()
            # Security: allowed_names has empty __builtins__ to prevent:
            # - Import statements (e.g., "import os")
            # - File operations (e.g., "open('/etc/passwd')")
            # - System calls (e.g., "os.system('rm -rf /')")
            # Only mathematical operators (+, -, *, /, %, **) are allowed
            allowed_names = {"__builtins__": {}}  # Empty builtins = no dangerous functions
            calculated_value = eval(expression, allowed_names, context)

            # STEP 5: Format the result based on format_type
            if format_type == "integer":
                calculated_value = int(round(calculated_value))
            elif format_type == "percent":
                calculated_value = round(calculated_value, 2)
            elif format_type == "currency":
                calculated_value = round(calculated_value, 2)
            else:  # number (default)
                # Smart rounding: keep as int if whole number, else 2 decimals
                calculated_value = round(calculated_value, 2) if calculated_value != int(calculated_value) else int(calculated_value)

            row[column_name] = {
                "value": calculated_value,
                "expression": expression,
                "format_type": format_type,
                "is_calculated": True
            }

        except ZeroDivisionError:
            row[column_name] = {
                "value": None,
                "expression": expression,
                "format_type": format_type,
                "is_calculated": True,
                "warning": "Division by zero"
            }
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")
            row[column_name] = {
                "value": None,
                "expression": expression,
                "format_type": format_type,
                "is_calculated": True,
                "warning": str(e)
            }

    # Add calculation metadata
    if "calculation_metadata" not in result:
        result["calculation_metadata"] = {
            "calculated_columns": [],
            "warnings": []
        }

    result["calculation_metadata"]["calculated_columns"].append({
        "name": column_name,
        "expression": expression,
        "format_type": format_type
    })

    if errors:
        result["calculation_metadata"]["warnings"].extend(errors[:5])

    # Update the stored result
    _last_query_result = result

    return result


def report_insight(
    insight_type: str,
    message: str,
) -> dict[str, str]:
    """Report a proactive insight discovered during data analysis.

    Call this tool whenever you identify a noteworthy pattern, anomaly,
    comparison, or suggestion while analyzing query results. Each call
    records one insight that will be displayed to the user as a visual
    badge alongside your text response.

    You may call this tool multiple times per response to report several
    insights. Insights should be concise (one sentence) and grounded in
    the data — do not speculate.

    Args:
        insight_type (str): Category of the insight. Must be one of:
            - "trend"      — A directional change over time or across categories
                             (e.g., revenue growing 15% month-over-month)
            - "anomaly"    — An unusual value that deviates from the norm
                             (e.g., a single store with 10x average sales)
            - "comparison" — A relative observation that adds context
                             (e.g., this quarter is 20% above the yearly average)
            - "suggestion" — A recommended follow-up query or analysis
                             (e.g., slicing the data by region could reveal more)
        message (str): A concise, actionable description of the insight.
            Should be one sentence and clearly supported by the data.
            Examples:
            - "Revenue has increased 23% month-over-month, the highest growth in Q4."
            - "Store #42 has unusually low revenue despite high foot traffic."
            - "This is 15% higher than the same period last year."
            - "Breaking this down by region could reveal geographic trends."

    Returns:
        dict[str, str]: Confirmation that the insight was recorded.
            {"status": "recorded", "type": "<insight_type>"}

    Side Effects:
        - Appends to the global _pending_insights list
        - NOT thread-safe (see _pending_insights documentation)

    Examples:
        >>> report_insight("trend", "Sales have grown 12% each quarter this year.")
        {"status": "recorded", "type": "trend"}

        >>> report_insight("anomaly", "Montana has 3x the per-capita spending of any other state.")
        {"status": "recorded", "type": "anomaly"}

        >>> report_insight("suggestion", "Comparing weekday vs weekend sales could surface staffing insights.")
        {"status": "recorded", "type": "suggestion"}
    """
    valid_types = {"trend", "anomaly", "comparison", "suggestion"}
    if insight_type not in valid_types:
        insight_type = "suggestion"

    _pending_insights.append({
        "type": insight_type,
        "message": message.strip(),
    })

    return {"status": "recorded", "type": insight_type}


def get_and_clear_pending_insights() -> list[dict[str, str]]:
    """Drain all pending insights accumulated during the current agent invocation.

    Called by the API route after the ADK event stream completes to collect
    insights reported via report_insight() tool calls.

    Returns:
        list[dict[str, str]]: List of insight dicts, each with "type" and "message".
            Returns an empty list if no insights were reported.

    Side Effects:
        - Clears the global _pending_insights list
    """
    insights = list(_pending_insights)
    _pending_insights.clear()
    return insights


# List of all tools to be registered with the main agent
# Note: apply_enrichment is NOT included here - it's only for the enrichment sub-agent
CUSTOM_TOOLS = [
    get_available_tables,
    get_table_schema,
    execute_query_with_metadata,
    clear_schema_cache,
    add_calculated_column,
    report_insight,
]
