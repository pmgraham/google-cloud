"""Enrichment Sub-Agent - Enriches query results with real-time data from Google Search.

This agent is designed with strict guardrails to ensure data quality and prevent
contamination of trusted database results with inaccurate or irrelevant information.
"""

from google.adk.agents import Agent
from google.adk.tools.google_search_tool import GoogleSearchTool

from ..callbacks import after_tool_callback
from ..tools import apply_enrichment
from .prompts import ENRICHMENT_INSTRUCTION

# Create GoogleSearchTool with bypass to allow multi-tool usage
# Without this, google_search cannot be combined with other tools in the same agent
_google_search = GoogleSearchTool(bypass_multi_tools_limit=True)


def create_enrichment_agent() -> Agent:
    """Create the enrichment sub-agent with Google Search and apply_enrichment.

    The agent uses google_search to gather data, then apply_enrichment to
    merge the results with the original query data.
    """
    return Agent(
        name="enrichment_agent",
        model="gemini-3-flash-preview",
        description=(
            "A data enrichment specialist that augments query results with "
            "verified real-time information from Google Search, then merges "
            "the enrichment into the query results using apply_enrichment."
        ),
        instruction=ENRICHMENT_INSTRUCTION,
        tools=[_google_search, apply_enrichment],
        after_tool_callback=after_tool_callback,
    )
