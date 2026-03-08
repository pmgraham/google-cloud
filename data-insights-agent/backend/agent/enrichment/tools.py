"""Enrichment Tools - Structured tools for requesting and validating data enrichment.

These tools provide a controlled interface for the main agent to request enrichment
from the enrichment sub-agent, with built-in validation and guardrails.
"""

from typing import Any
from pydantic import BaseModel, Field
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Confidence level for enriched data."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FreshnessLevel(str, Enum):
    """Freshness level for enriched data."""
    STATIC = "static"      # Data that doesn't change (historical facts)
    CURRENT = "current"    # Recently verified (<1 year)
    DATED = "dated"        # May be outdated (1-3 years)
    STALE = "stale"        # Likely outdated (>3 years for dynamic data)


class EnrichedField(BaseModel):
    """A single enriched data field with metadata."""
    value: Any
    source: str
    confidence: ConfidenceLevel
    freshness: FreshnessLevel
    warning: str | None = None


class EnrichmentResult(BaseModel):
    """Result of enriching a single data value."""
    original_value: str
    enriched_fields: dict[str, EnrichedField]


class EnrichmentResponse(BaseModel):
    """Complete enrichment response with all results and metadata."""
    enrichments: list[EnrichmentResult]
    warnings: list[str] = Field(default_factory=list)
    search_performed: bool = True
    partial_failure: bool = False  # True if some enrichments failed


# Validation functions for guardrails

def validate_enrichment_request(
    values: list[str],
    fields: list[str],
    data_type: str | None = None
) -> dict[str, Any]:
    """Validate an enrichment request against guardrails before sending to enrichment agent.

    Enforces limits on the number of values and fields to prevent excessive API calls,
    long processing times, and unreliable enrichment results. Also provides warnings
    for dynamic fields that may become outdated.

    **GUARDRAILS** (System-wide limits):
    - **Maximum 20 unique values** can be enriched per request
    - **Maximum 5 fields** can be added per value
    - These limits prevent API quota exhaustion and ensure reasonable response times

    Args:
        values (list[str]): List of unique values to enrich.
            Examples: ["CA", "TX", "NY"], ["Microsoft", "Apple", "Google"]
        fields (list[str]): List of fields to add for each value.
            Examples: ["capital", "population"], ["CEO", "founded_year", "headquarters"]
        data_type (str | None, optional): Optional data type hint for context.
            Examples: "us_state", "city", "company", "hotel"
            Currently unused but reserved for future template-based validation.

    Returns:
        dict[str, Any]: Validation result with the following structure:

            On success:
            {
                "valid": True,
                "error": None,
                "warnings": [
                    "Dynamic fields requested: ['population']. These may change over time...",
                    "Large enrichment request (60 total lookups). This may take longer..."
                ],
                "total_enrichments": 60  # len(values) * len(fields)
            }

            On failure:
            {
                "valid": False,
                "error": "Too many values to enrich. Maximum is 20, got 25...",
                "warnings": []
            }

    Examples:
        >>> # Valid request
        >>> result = validate_enrichment_request(["CA", "TX", "NY"], ["capital", "population"])
        >>> result
        {"valid": True, "error": None, "warnings": [...], "total_enrichments": 6}

        >>> # Too many values
        >>> result = validate_enrichment_request(list(range(25)), ["capital"])
        >>> result
        {"valid": False, "error": "Too many values to enrich. Maximum is 20, got 25...", "warnings": []}

        >>> # Too many fields
        >>> result = validate_enrichment_request(["CA"], ["capital", "population", "gdp", "area", "governor", "flag"])
        >>> result
        {"valid": False, "error": "Too many fields requested. Maximum is 5, got 6...", "warnings": []}

        >>> # Warning for dynamic fields
        >>> result = validate_enrichment_request(["CA"], ["population", "governor"])
        >>> result["warnings"]
        ["Dynamic fields requested: ['population', 'governor']. These may change over time..."]

    Notes:
        - Guardrails are enforced BEFORE calling the enrichment agent
        - Warnings do not prevent request execution, only inform about potential issues
        - Large requests (>30 total lookups) receive a warning but are not blocked
    """
    warnings = []

    # ========== GUARDRAIL 1: Maximum Values Limit ==========
    # Limit number of values to prevent excessive API calls
    # Example: Enriching 100 states with 5 fields = 500 Google Search API calls
    # Rationale: API quota limits, response time, and reliability
    MAX_VALUES = 20
    if len(values) > MAX_VALUES:
        return {
            "valid": False,
            "error": f"Too many values to enrich. Maximum is {MAX_VALUES}, got {len(values)}. "
                     f"Please narrow your query or enrich in batches.",
            "warnings": []
        }

    # ========== GUARDRAIL 2: Maximum Fields Limit ==========
    # Limit number of fields per value to keep responses manageable
    # Rationale: More fields = more searches = higher failure rate and slower response
    MAX_FIELDS = 5
    if len(fields) > MAX_FIELDS:
        return {
            "valid": False,
            "error": f"Too many fields requested. Maximum is {MAX_FIELDS}, got {len(fields)}. "
                     f"Please request fewer enrichment fields.",
            "warnings": []
        }

    # Guardrail: Check for empty requests
    if not values:
        return {
            "valid": False,
            "error": "No values provided for enrichment.",
            "warnings": []
        }

    if not fields:
        return {
            "valid": False,
            "error": "No fields specified for enrichment. Please specify what data to add.",
            "warnings": []
        }

    # Warning: Dynamic fields that may be outdated
    dynamic_field_indicators = ["population", "governor", "ceo", "current", "recent", "news", "events"]
    dynamic_fields_requested = [f for f in fields if any(ind in f.lower() for ind in dynamic_field_indicators)]
    if dynamic_fields_requested:
        warnings.append(
            f"Dynamic fields requested: {dynamic_fields_requested}. "
            f"These may change over time - results will include freshness indicators."
        )

    # Warning: Large enrichment request
    total_enrichments = len(values) * len(fields)
    if total_enrichments > 30:
        warnings.append(
            f"Large enrichment request ({total_enrichments} total lookups). "
            f"This may take longer and could have some failures."
        )

    return {
        "valid": True,
        "error": None,
        "warnings": warnings,
        "total_enrichments": total_enrichments
    }


def format_enrichment_request(
    column_name: str,
    values: list[str],
    fields: list[str],
    context: str | None = None
) -> str:
    """
    Format an enrichment request as a structured prompt for the enrichment agent.

    Args:
        column_name: Name of the column being enriched (e.g., "state_code")
        values: Unique values to enrich
        fields: Fields to add for each value
        context: Optional context about the data

    Returns:
        Formatted prompt string for the enrichment agent
    """
    prompt = f"""## Enrichment Request

**Column to enrich**: {column_name}
**Values**: {', '.join(values[:10])}{'...' if len(values) > 10 else ''}
**Fields to add**: {', '.join(fields)}

{f'**Context**: {context}' if context else ''}

Please enrich each value with the requested fields. For each field:
1. Search Google for accurate, current information
2. Include the source for each fact
3. Indicate confidence level (high/medium/low)
4. Flag any information that may be outdated

Return results in the structured JSON format specified in your instructions.
"""
    return prompt


def parse_enrichment_response(response_text: str) -> EnrichmentResponse | None:
    """
    Parse the enrichment agent's response into a structured format.

    Args:
        response_text: Raw text response from the enrichment agent

    Returns:
        EnrichmentResponse object or None if parsing fails
    """
    import json
    import re

    # Try to extract JSON from the response
    json_match = re.search(r'\{[\s\S]*"enrichments"[\s\S]*\}', response_text)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group())

        # Convert to structured objects
        enrichments = []
        for item in data.get("enrichments", []):
            enriched_fields = {}
            for field_name, field_data in item.get("enriched_fields", {}).items():
                if isinstance(field_data, dict):
                    enriched_fields[field_name] = EnrichedField(
                        value=field_data.get("value"),
                        source=field_data.get("source", "Unknown"),
                        confidence=ConfidenceLevel(field_data.get("confidence", "medium")),
                        freshness=FreshnessLevel(field_data.get("freshness", "current")),
                        warning=field_data.get("warning")
                    )

            enrichments.append(EnrichmentResult(
                original_value=item.get("original_value", ""),
                enriched_fields=enriched_fields
            ))

        return EnrichmentResponse(
            enrichments=enrichments,
            warnings=data.get("warnings", []),
            search_performed=data.get("search_performed", True),
            partial_failure=data.get("partial_failure", False)
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Failed to parse enrichment response: {e}")
        return None


def merge_enrichment_with_results(
    query_results: dict[str, Any],
    enrichment: EnrichmentResponse,
    source_column: str
) -> dict[str, Any]:
    """
    Merge enrichment data with original query results.

    Args:
        query_results: Original query results from BigQuery
        enrichment: Parsed enrichment response
        source_column: Column name that was enriched

    Returns:
        Updated query results with enrichment data added
    """
    if not enrichment or not enrichment.enrichments:
        return query_results

    # Create lookup map from original value to enrichment
    enrichment_map = {e.original_value: e for e in enrichment.enrichments}

    # Get the list of enriched field names
    enriched_field_names = set()
    for e in enrichment.enrichments:
        enriched_field_names.update(e.enriched_fields.keys())

    # Add new columns to the schema
    new_columns = []
    for field_name in sorted(enriched_field_names):
        new_columns.append({
            "name": f"_enriched_{field_name}",
            "type": "STRING",
            "is_enriched": True
        })

    query_results["columns"].extend(new_columns)

    # Add enriched data to each row
    for row in query_results.get("rows", []):
        source_value = str(row.get(source_column, ""))
        enrichment_data = enrichment_map.get(source_value)

        if enrichment_data:
            for field_name, field_data in enrichment_data.enriched_fields.items():
                # Include source and confidence in the display value
                display_value = field_data.value
                if field_data.warning:
                    display_value = f"{display_value} ⚠️"

                row[f"_enriched_{field_name}"] = {
                    "value": display_value,
                    "source": field_data.source,
                    "confidence": field_data.confidence.value,
                    "freshness": field_data.freshness.value,
                    "warning": field_data.warning
                }
        else:
            # No enrichment found for this value
            for field_name in enriched_field_names:
                row[f"_enriched_{field_name}"] = {
                    "value": None,
                    "source": None,
                    "confidence": None,
                    "freshness": None,
                    "warning": "No enrichment data found"
                }

    # Add enrichment metadata
    query_results["enrichment_metadata"] = {
        "source_column": source_column,
        "enriched_fields": list(enriched_field_names),
        "total_enriched": len(enrichment.enrichments),
        "warnings": enrichment.warnings,
        "partial_failure": enrichment.partial_failure
    }

    return query_results


# Tool function for the main agent to request enrichment
def request_enrichment(
    column_name: str,
    unique_values: list[str],
    fields_to_add: list[str],
    data_type: str | None = None,
    context: str | None = None
) -> dict[str, Any]:
    """
    Request enrichment for query result values. This tool validates the request
    and prepares it for the enrichment sub-agent.

    Args:
        column_name: The column containing values to enrich (e.g., "state_code")
        unique_values: List of unique values from that column to enrich
        fields_to_add: What information to add (e.g., ["capital", "population", "famous_people"])
        data_type: Optional hint about data type ("us_state", "city", "company", "hotel")
        context: Optional context to help with accurate enrichment

    Returns:
        dict with:
        - status: "ready" if request is valid, "error" if not
        - prompt: Formatted prompt for the enrichment agent (if ready)
        - warnings: Any warnings about the request
        - error: Error message (if status is "error")
    """
    # Validate the request
    validation = validate_enrichment_request(unique_values, fields_to_add, data_type)

    if not validation["valid"]:
        return {
            "status": "error",
            "error": validation["error"],
            "warnings": validation["warnings"]
        }

    # Format the enrichment prompt
    prompt = format_enrichment_request(
        column_name=column_name,
        values=unique_values,
        fields=fields_to_add,
        context=context
    )

    return {
        "status": "ready",
        "prompt": prompt,
        "warnings": validation["warnings"],
        "total_enrichments": validation["total_enrichments"],
        "instructions": (
            "Transfer to the enrichment_agent with this prompt. "
            "The enrichment agent will search Google and return structured data. "
            "After receiving the response, merge it with the query results."
        )
    }
