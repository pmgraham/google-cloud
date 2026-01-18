"""Custom tools for the Data Insights Agent."""

from typing import Any
from google.cloud import bigquery
from .config import settings


# Cache for schema information to improve response times
_schema_cache: dict[str, dict] = {}

# Store the last query result for enrichment merging
_last_query_result: dict[str, Any] | None = None


def get_available_tables() -> dict[str, Any]:
    """
    Get a list of all available tables in the configured BigQuery dataset
    with their descriptions and column information.

    Returns:
        dict: A dictionary containing:
            - status: "success" or "error"
            - dataset: The dataset name
            - tables: List of table information including name, description, and columns
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
    """
    Validate a SQL query without executing it using BigQuery's dry run feature.
    This helps catch errors before running potentially expensive queries.

    Args:
        sql: The SQL query to validate

    Returns:
        dict: A dictionary containing:
            - status: "valid" or "invalid"
            - estimated_bytes: Estimated bytes to be processed (if valid)
            - error: Error message (if invalid)
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
    """
    Execute a SQL query and return results with metadata for the frontend.

    Args:
        sql: The SQL query to execute
        max_rows: Maximum number of rows to return (default 1000)

    Returns:
        dict: A dictionary containing:
            - status: "success" or "error"
            - columns: List of column names and types
            - rows: The query results as a list of dictionaries
            - total_rows: Total rows in result
            - query_time_ms: Query execution time in milliseconds
            - sql: The executed SQL query
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
    """
    Apply enrichment data to the last query result and return merged results.
    Call this AFTER the enrichment_agent has returned with the enrichment data.

    Args:
        source_column: The column name that was enriched (e.g., "state", "city")
        enrichment_data: List of enrichment objects from the enrichment agent.
            Each object should have:
            - original_value: The value that was enriched (e.g., "CA", "Texas")
            - enriched_fields: Dict of field_name -> {value, source, confidence, freshness, warning}

    Example enrichment_data:
        [
            {
                "original_value": "CA",
                "enriched_fields": {
                    "capital": {"value": "Sacramento", "source": "Google", "confidence": "high", "freshness": "static"},
                    "population": {"value": "39.5 million", "source": "US Census", "confidence": "medium", "freshness": "current"}
                }
            },
            ...
        ]

    Returns:
        dict: Merged query result with enrichment columns added, ready for frontend display.
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

    # Create a deep copy of the last query result
    import copy
    result = copy.deepcopy(_last_query_result)

    # Build a lookup map from original value to enrichment data
    enrichment_map = {}
    enriched_field_names = set()

    for item in enrichment_data:
        original_value = item.get("original_value", "")
        enriched_fields = item.get("enriched_fields", {})
        enrichment_map[original_value] = enriched_fields
        enriched_field_names.update(enriched_fields.keys())

    # Add enriched columns to the schema
    for field_name in sorted(enriched_field_names):
        result["columns"].append({
            "name": f"_enriched_{field_name}",
            "type": "STRING",
            "is_enriched": True
        })

    # Add enriched data to each row
    warnings = []
    for row in result.get("rows", []):
        source_value = str(row.get(source_column, ""))
        enrichment = enrichment_map.get(source_value)

        if enrichment:
            for field_name in enriched_field_names:
                field_data = enrichment.get(field_name)
                if field_data:
                    row[f"_enriched_{field_name}"] = {
                        "value": field_data.get("value"),
                        "source": field_data.get("source"),
                        "confidence": field_data.get("confidence", "medium"),
                        "freshness": field_data.get("freshness", "current"),
                        "warning": field_data.get("warning")
                    }
                else:
                    row[f"_enriched_{field_name}"] = {
                        "value": None,
                        "source": None,
                        "confidence": None,
                        "freshness": None,
                        "warning": "Field not found in enrichment"
                    }
        else:
            # No enrichment found for this row's source value
            for field_name in enriched_field_names:
                row[f"_enriched_{field_name}"] = {
                    "value": None,
                    "source": None,
                    "confidence": None,
                    "freshness": None,
                    "warning": f"No enrichment data found for '{source_value}'"
                }
            if source_value and source_value not in [w.split("'")[1] for w in warnings if "'" in w]:
                warnings.append(f"No enrichment data found for '{source_value}'")

    # Add enrichment metadata
    result["enrichment_metadata"] = {
        "source_column": source_column,
        "enriched_fields": list(enriched_field_names),
        "total_enriched": len(enrichment_map),
        "warnings": warnings[:5],  # Limit warnings
        "partial_failure": len(warnings) > 0
    }

    # Update the stored result so add_calculated_column can use enriched data
    _last_query_result = result

    return result


def add_calculated_column(
    column_name: str,
    expression: str,
    format_type: str = "number"
) -> dict[str, Any]:
    """
    Add a calculated column to the last query result without re-running the query.
    Use this when the user wants a derived value from existing columns.

    Args:
        column_name: Name for the new calculated column (e.g., "residents_per_store")
        expression: Math expression using existing column names (e.g., "population / store_count")
                   Supported operators: +, -, *, /, %, **
                   For enriched columns, use the _enriched_ prefix (e.g., "_enriched_population")
                   To access the value of an enriched column, the expression parser will
                   automatically extract the 'value' field.
        format_type: How to format the result - "number", "percent", "currency", or "integer"

    Example expressions:
        - "population / store_count" → residents per store
        - "revenue - costs" → profit
        - "(new_customers / total_customers) * 100" → new customer percentage
        - "_enriched_population / store_count" → using enriched population data

    Returns:
        dict: Updated query result with the new calculated column added.
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

    # Get available column names for validation
    available_columns = {col["name"] for col in result["columns"]}

    # Parse expression to find column references
    # Match word characters that could be column names (including _enriched_ prefix)
    potential_columns = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expression))

    # Filter to only actual columns (exclude Python keywords and functions)
    excluded = {'and', 'or', 'not', 'if', 'else', 'True', 'False', 'None', 'in', 'is'}
    referenced_columns = potential_columns - excluded

    # Check all referenced columns exist
    missing_columns = referenced_columns - available_columns
    if missing_columns:
        return {
            "status": "error",
            "error": f"Column(s) not found: {', '.join(missing_columns)}. "
                     f"Available columns: {', '.join(sorted(available_columns))}"
        }

    # Add the new column to schema
    result["columns"].append({
        "name": column_name,
        "type": "FLOAT64" if format_type != "integer" else "INTEGER",
        "is_calculated": True
    })

    # Calculate values for each row
    errors = []
    for i, row in enumerate(result.get("rows", [])):
        try:
            # Build a context dict for eval with column values
            context = {}
            for col in referenced_columns:
                value = row.get(col)
                # Handle enriched columns - extract the value field
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]
                # Convert to float for calculation, handle None
                if value is None:
                    context[col] = 0  # or could use None and skip
                elif isinstance(value, str):
                    # Try to parse numbers from strings (e.g., "39.5 million")
                    clean_val = re.sub(r'[^\d.]+', '', value.split()[0] if value else '0')
                    try:
                        context[col] = float(clean_val) if clean_val else 0
                    except ValueError:
                        context[col] = 0
                else:
                    context[col] = float(value)

            # Safely evaluate the expression
            # Only allow basic math operations
            allowed_names = {"__builtins__": {}}
            calculated_value = eval(expression, allowed_names, context)

            # Format the result
            if format_type == "integer":
                calculated_value = int(round(calculated_value))
            elif format_type == "percent":
                calculated_value = round(calculated_value, 2)
            elif format_type == "currency":
                calculated_value = round(calculated_value, 2)
            else:  # number
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


# List of all tools to be registered with the agent
CUSTOM_TOOLS = [
    get_available_tables,
    get_table_schema,
    validate_sql_query,
    execute_query_with_metadata,
    clear_schema_cache,
    apply_enrichment,
    add_calculated_column
]
