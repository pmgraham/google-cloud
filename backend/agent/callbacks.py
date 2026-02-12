"""ADK callbacks for deterministic tool-call validation and response guarding.

This module provides ``before_tool_callback`` and ``after_tool_callback``
hooks that the Google ADK Agent invokes around every tool call.  Unlike
prompt-based suggestions, these callbacks are **deterministic** – the LLM
cannot bypass them.

before_tool_callback
    Intercepts ``execute_query_with_metadata`` calls and runs a BigQuery
    dry-run validation *before* the query reaches BigQuery.  Invalid SQL
    is short-circuited with a clean error dict so the model can fix it.

after_tool_callback
    Runs after every tool call and validates that structured-response tools
    (``execute_query_with_metadata``, ``apply_enrichment``,
    ``add_calculated_column``) return well-formed dicts.  Malformed
    responses are replaced with a sanitised error so the model receives a
    predictable signal.
"""

from typing import Any, Optional

from google.adk.tools import BaseTool, ToolContext

from .tools import validate_sql_query

# Tools whose responses carry structured query data that the frontend and
# downstream tools (enrichment, calculated columns) depend on.
_STRUCTURED_RESPONSE_TOOLS = frozenset(
    {
        "execute_query_with_metadata",
        "apply_enrichment",
        "add_calculated_column",
    }
)


async def before_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """SQL validation gate – fires before every tool call.

    For ``execute_query_with_metadata``, extracts the ``sql`` argument and
    performs a BigQuery dry-run via ``validate_sql_query``.  If validation
    fails the tool call is short-circuited: the returned error dict becomes
    the tool response and BigQuery is never hit.

    For all other tools this callback returns ``None`` (no-op) so ADK
    proceeds normally.
    """
    if tool.name != "execute_query_with_metadata":
        return None

    sql = args.get("sql", "")
    if not sql:
        return {
            "status": "error",
            "error": "No SQL query provided.",
            "sql": "",
        }

    validation = validate_sql_query(sql)

    if validation.get("status") == "invalid":
        return {
            "status": "error",
            "error": f"SQL validation failed: {validation['error']}",
            "sql": sql,
        }

    # Validation passed – let ADK call the real tool.
    return None


async def after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> Optional[dict]:
    """Response structure guard – fires after every tool call.

    For structured-response tools (``execute_query_with_metadata``,
    ``apply_enrichment``, ``add_calculated_column``), validates that the
    response is a dict with a ``status`` field.  On ``status == "success"``
    it further checks that ``rows`` and ``columns`` are lists.

    Malformed responses are replaced with a sanitised error dict.  All
    other tools pass through unchanged (``None`` return).
    """
    if tool.name not in _STRUCTURED_RESPONSE_TOOLS:
        return None

    # Guard: response must be a dict
    if not isinstance(tool_response, dict):
        return {
            "status": "error",
            "error": (
                f"Tool '{tool.name}' returned an unexpected response type "
                f"({type(tool_response).__name__}). Expected a dict."
            ),
        }

    # Guard: response must contain a status field
    if "status" not in tool_response:
        return {
            "status": "error",
            "error": (
                f"Tool '{tool.name}' response is missing the 'status' field."
            ),
        }

    # For successful responses, validate the data payload
    if tool_response["status"] == "success":
        rows = tool_response.get("rows")
        columns = tool_response.get("columns")

        if not isinstance(rows, list):
            return {
                "status": "error",
                "error": (
                    f"Tool '{tool.name}' returned a success response but "
                    f"'rows' is not a list (got {type(rows).__name__})."
                ),
            }

        if not isinstance(columns, list):
            return {
                "status": "error",
                "error": (
                    f"Tool '{tool.name}' returned a success response but "
                    f"'columns' is not a list (got {type(columns).__name__})."
                ),
            }

    # Response looks well-formed – pass through unchanged.
    return None
