"""DataGrunt Agent — ADK entry point.

Exports root_agent as required by the Google ADK framework.
Run with: adk web datagrunt_agent
"""

import os
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from datagrunt_agent.prompts.coordinator import COORDINATOR_PROMPT
from datagrunt_agent.prompts.data_cleaner import DATA_CLEANER_PROMPT
from datagrunt_agent.prompts.profiler import PROFILER_PROMPT
from datagrunt_agent.prompts.quality_analyst import QUALITY_ANALYST_PROMPT
from datagrunt_agent.prompts.schema_architect import SCHEMA_ARCHITECT_PROMPT
from datagrunt_agent.tools import (
    cleaning,
    cleaning_report,
    export,
    ingestion,
    profiling,
    quality,
    report,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Model Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Specialist Agents
# ---------------------------------------------------------------------------

profiler_agent = Agent(
    name="Profiler",
    description=(
        "Analyzes table schemas and column statistics. Returns types, null rates, "
        "cardinality, and type coercion recommendations for all columns in one call."
    ),
    model=os.getenv("PROFILER_MODEL", DEFAULT_MODEL),
    instruction=PROFILER_PROMPT,
    tools=[
        FunctionTool(func=profiling.profile_columns),
        FunctionTool(func=profiling.profile_table),
        FunctionTool(func=profiling.sample_data),
    ],
)

schema_architect_agent = Agent(
    name="SchemaArchitect",
    description=(
        "Handles schema detection, schema evolution, and canonical schema "
        "transformation. Compares schemas, detects type changes, proposes "
        "unified canonical schemas from multiple sources."
    ),
    model=os.getenv("SCHEMA_ARCHITECT_MODEL", "gemini-2.5-pro"),
    instruction=SCHEMA_ARCHITECT_PROMPT,
    tools=[
        # Phase 2 tools will be added here
    ],
)

quality_analyst_agent = Agent(
    name="QualityAnalyst",
    description=(
        "Observational data quality auditing: type analysis, null patterns, "
        "null-like strings, whitespace issues, duplicates, constant columns, "
        "and outlier detection. Reports findings but never modifies data."
    ),
    model=os.getenv("QUALITY_ANALYST_MODEL", DEFAULT_MODEL),
    instruction=QUALITY_ANALYST_PROMPT,
    tools=[
        FunctionTool(func=quality.quality_report),
        FunctionTool(func=report.export_quality_report),
    ],
)

data_cleaner_agent = Agent(
    name="DataCleaner",
    description=(
        "Data cleaning: fixes quality issues in-place based on Quality Analyst "
        "findings. Handles encoding, whitespace, null normalization, date "
        "standardization, type coercion, dedup flagging, PII detection, and "
        "produces a structured cleaning report."
    ),
    model=os.getenv("DATA_CLEANER_MODEL", DEFAULT_MODEL),
    instruction=DATA_CLEANER_PROMPT,
    tools=[
        FunctionTool(func=cleaning.clean_table),
        FunctionTool(func=cleaning_report.export_cleaning_report),
    ],
)

# ---------------------------------------------------------------------------
# Actionable finding categories that warrant cleaning
# ---------------------------------------------------------------------------

_ACTIONABLE_CATEGORIES = {
    "null_like_strings",
    "whitespace",
    "type_analysis",
    "duplicates",
    "constant_columns",
    "null_analysis",
}

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def _after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> dict | None:
    """Inject next_action directives for pipeline auto-chaining.

    Handles two transitions:
    1. load_file (success) → delegate to Quality Analyst
    2. QualityAnalyst (with actionable findings) → delegate to Data Cleaner
    """
    # --- load_file → Quality Analyst ---
    if tool.name == "load_file" and isinstance(tool_response, dict):
        if tool_response.get("status") == "success":
            table_name = tool_response.get("table_name")
            tool_response["next_action"] = {
                "action": "delegate_to_quality_analyst",
                "table_name": table_name,
                "instruction": (
                    "Immediately delegate to the Quality Analyst agent "
                    f"to run quality_report on '{table_name}'. "
                    "Do not wait for user input."
                ),
            }
        return None

    # --- QualityAnalyst → Data Cleaner ---
    if tool.name == "QualityAnalyst":
        findings = tool_context.state.get("quality_findings", [])
        table_name = tool_context.state.get("quality_table_name", "")

        actionable = [
            f for f in findings
            if f.get("category") in _ACTIONABLE_CATEGORIES
        ]

        if actionable and table_name:
            # QualityAnalyst returns text to the coordinator. ADK requires
            # the callback return value to be a string (Gemini Part).
            # Append a next_action directive as text so the coordinator
            # follows it like the load_file → QualityAnalyst chain.
            import json
            next_action = {
                "action": "delegate_to_data_cleaner",
                "table_name": table_name,
                "instruction": (
                    "Immediately delegate to the Data Cleaner agent "
                    f"to run clean_table on '{table_name}'. "
                    "Do not wait for user input."
                ),
            }
            return (
                f"{tool_response}\n\n"
                f"next_action: {json.dumps(next_action)}"
            )

    return None


# ---------------------------------------------------------------------------
# Coordinator Agent (root_agent — the ADK entry point)
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="DataGrunt",
    description=(
        "Data engineering agent. Loads files (CSV, JSON, Parquet, Excel), "
        "profiles schemas, detects data quality issues, cleans data, and "
        "exports to multiple formats. Coordinates specialist agents."
    ),
    model=os.getenv("COORDINATOR_MODEL", DEFAULT_MODEL),
    instruction=COORDINATOR_PROMPT,
    after_tool_callback=_after_tool_callback,
    tools=[
        # Sub-agents
        AgentTool(agent=profiler_agent),
        AgentTool(agent=schema_architect_agent),
        AgentTool(agent=quality_analyst_agent),
        AgentTool(agent=data_cleaner_agent),
        # Direct tools — Ingestion
        FunctionTool(func=ingestion.load_file),
        FunctionTool(func=ingestion.detect_format),
        FunctionTool(func=ingestion.list_tables),
        FunctionTool(func=ingestion.inspect_raw_file),
        # Direct tools — Export
        FunctionTool(func=export.export_csv),
        FunctionTool(func=export.export_parquet),
        FunctionTool(func=export.export_json),
        FunctionTool(func=export.export_jsonl),
        FunctionTool(func=export.export_excel),
        # Direct tools — Report
        FunctionTool(func=report.export_quality_report),
        FunctionTool(func=cleaning_report.export_cleaning_report),
        # Direct tools — Quick profiling
        FunctionTool(func=profiling.sample_data),
    ],
)
