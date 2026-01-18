"""Enrichment Sub-Agent Package.

This package provides data enrichment capabilities using Google Search
to augment query results with real-time information.
"""

from .agent import create_enrichment_agent
from .prompts import (
    ENRICHMENT_INSTRUCTION,
    ENRICHMENT_TEMPLATES,
    get_enrichment_template,
    get_available_enrichment_fields,
)
from .tools import (
    request_enrichment,
    validate_enrichment_request,
    format_enrichment_request,
    parse_enrichment_response,
    merge_enrichment_with_results,
    ConfidenceLevel,
    FreshnessLevel,
    EnrichedField,
    EnrichmentResult,
    EnrichmentResponse,
)

__all__ = [
    # Agent
    "create_enrichment_agent",
    # Prompts
    "ENRICHMENT_INSTRUCTION",
    "ENRICHMENT_TEMPLATES",
    "get_enrichment_template",
    "get_available_enrichment_fields",
    # Tools
    "request_enrichment",
    "validate_enrichment_request",
    "format_enrichment_request",
    "parse_enrichment_response",
    "merge_enrichment_with_results",
    # Types
    "ConfidenceLevel",
    "FreshnessLevel",
    "EnrichedField",
    "EnrichmentResult",
    "EnrichmentResponse",
]
