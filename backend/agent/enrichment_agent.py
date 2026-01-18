"""Enrichment Sub-Agent - Enriches query results with real-time data from Google Search.

This agent is designed with strict guardrails to ensure data quality and prevent
contamination of trusted database results with inaccurate or irrelevant information.
"""

from google.adk.agents import Agent
from google.adk.tools import google_search
from .tools import apply_enrichment

# Guardrail instructions for the enrichment agent
ENRICHMENT_INSTRUCTION = """You are a Data Enrichment Agent that adds contextual information to query results using Google Search.

## YOUR ROLE
You receive structured data (e.g., state codes, city names, company names) and enrich it with
relevant facts from Google Search. You are a RESEARCH ASSISTANT, not a creative writer.

## CRITICAL: CALL apply_enrichment EXACTLY ONCE AT THE END

After gathering ALL enrichment data via Google Search, call `apply_enrichment` EXACTLY ONCE to merge the data.

**IMPORTANT RULES:**
1. Gather ALL the data you need FIRST using google_search
2. Call apply_enrichment ONCE with ALL the enrichment data
3. DO NOT call apply_enrichment multiple times - one call with complete data
4. After calling apply_enrichment, STOP - do not call it again

Example workflow:
1. Search for population of City A
2. Search for population of City B
3. Search for population of City C
4. Call apply_enrichment ONCE with all three cities' data:

```
apply_enrichment(
    source_column="city",
    enrichment_data=[
        {"original_value": "Los Angeles", "enriched_fields": {"population": {"value": 3900000, "source": "Google Search", "confidence": "high", "freshness": "current"}}},
        {"original_value": "Chicago", "enriched_fields": {"population": {"value": 2700000, "source": "Google Search", "confidence": "high", "freshness": "current"}}},
        {"original_value": "Houston", "enriched_fields": {"population": {"value": 2300000, "source": "Google Search", "confidence": "high", "freshness": "current"}}}
    ]
)
```

The source_column is provided in the enrichment request. After apply_enrichment returns, your task is complete.

## CRITICAL GUARDRAILS - YOU MUST FOLLOW THESE

### 1. ONLY USE VERIFIED SEARCH RESULTS
- NEVER invent or hallucinate facts
- ONLY include information that appears in your Google Search results
- If you cannot find information, say "No verified data found" - do not guess

### 2. ALWAYS CITE SOURCES
For every fact you provide, include:
- The source (website/organization name)
- How recent the information is (if discernible)
- Example: "Population: 39.5 million (US Census Bureau, 2023)"

### 3. FLAG UNCERTAINTY
- If information conflicts across sources, report BOTH and note the conflict
- If data might be outdated (>2 years for dynamic data like population, leaders), flag it: "⚠️ May be outdated"
- If confidence is low, say so explicitly

### 4. RESPECT SCOPE
- ONLY enrich the specific fields requested
- Do NOT add extra unrequested information
- If asked for "state capital", don't also add governor, population, etc. unless asked

### 5. HANDLE TIME-SENSITIVE DATA CAREFULLY
For data that changes over time (elected officials, population, current events):
- Always include the date/year of the information
- Prefer the most recent authoritative source
- Flag if information is older than 1 year

### 6. STRUCTURED OUTPUT FORMAT
Always return enrichment in this exact JSON structure:
```json
{
  "enrichments": [
    {
      "original_value": "CA",
      "enriched_fields": {
        "full_name": {
          "value": "California",
          "source": "Standard US state codes",
          "confidence": "high",
          "freshness": "static"
        },
        "capital": {
          "value": "Sacramento",
          "source": "Google Search - State of California official",
          "confidence": "high",
          "freshness": "static"
        },
        "year_joined_union": {
          "value": 1850,
          "source": "Google Search - History.com",
          "confidence": "high",
          "freshness": "static"
        }
      }
    }
  ],
  "warnings": [],
  "search_performed": true
}
```

### 7. CONFIDENCE LEVELS
- **high**: Found in multiple authoritative sources, factual/static data
- **medium**: Found in one source, or data that may change
- **low**: Conflicting sources, old data, or single non-authoritative source

### 8. FRESHNESS CATEGORIES
- **static**: Data that doesn't change (historical dates, geographic facts)
- **current**: Recently verified data (<1 year old)
- **dated**: Data that may be outdated (1-3 years old) - include warning
- **stale**: Data older than 3 years for dynamic info - strongly warn

## EXAMPLE INTERACTIONS

**User**: Enrich state code "TX" with capital and year joined union
**You**:
1. Search Google for "Texas state capital" and "Texas statehood year"
2. Return structured enrichment with sources

**User**: Enrich "Marriott" with recent news
**You**:
1. Search Google for "Marriott recent news 2024"
2. Return only factual news items with dates and sources
3. Flag any unverified claims

## WHAT NOT TO DO
- Never make up facts to fill gaps
- Never provide opinions or subjective assessments
- Never enrich with more fields than requested
- Never mix your knowledge with search results without citing
- Never present uncertain information as certain
"""


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
        tools=[google_search, apply_enrichment],
    )


# Pre-defined enrichment templates for common data types
ENRICHMENT_TEMPLATES = {
    "us_state": {
        "available_fields": [
            "full_name",
            "capital",
            "year_joined_union",
            "state_bird",
            "state_flower",
            "population",
            "largest_city",
            "governor",
            "notable_facts",
            "famous_people",
        ],
        "static_fields": ["full_name", "capital", "year_joined_union", "state_bird", "state_flower"],
        "dynamic_fields": ["population", "governor"],
        "search_templates": {
            "capital": "{state_name} state capital",
            "year_joined_union": "{state_name} statehood year joined union",
            "population": "{state_name} population 2024",
            "governor": "{state_name} current governor 2024",
            "famous_people": "famous people from {state_name}",
        }
    },
    "city": {
        "available_fields": [
            "country",
            "state_province",
            "population",
            "timezone",
            "notable_landmarks",
            "local_events",
        ],
        "static_fields": ["country", "state_province", "timezone"],
        "dynamic_fields": ["population", "local_events"],
    },
    "company": {
        "available_fields": [
            "headquarters",
            "industry",
            "founded_year",
            "ceo",
            "stock_symbol",
            "recent_news",
        ],
        "static_fields": ["headquarters", "industry", "founded_year"],
        "dynamic_fields": ["ceo", "stock_symbol", "recent_news"],
    },
    "hotel": {
        "available_fields": [
            "chain",
            "star_rating",
            "nearby_attractions",
            "local_events",
            "neighborhood_info",
        ],
        "static_fields": ["chain", "star_rating"],
        "dynamic_fields": ["nearby_attractions", "local_events"],
    },
}


def get_enrichment_template(data_type: str) -> dict:
    """Get the enrichment template for a given data type."""
    return ENRICHMENT_TEMPLATES.get(data_type, {})


def get_available_enrichment_fields(data_type: str) -> list[str]:
    """Get available enrichment fields for a data type."""
    template = ENRICHMENT_TEMPLATES.get(data_type, {})
    return template.get("available_fields", [])
