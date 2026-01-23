"""Data Insights Agent - Main agent definition using Google ADK.

This module creates and configures the root agent for the Data Insights Agent
application using Google's Agent Development Kit (ADK). It sets up a two-agent
architecture with a main agent for query handling and a sub-agent for data enrichment.

**Architecture**:
- Main Agent: Handles user queries, SQL generation, query execution, calculations
- Enrichment Sub-Agent: Augments results with real-time data from Google Search

**Environment Setup**:
This module configures environment variables required for Vertex AI integration.
These settings must be set BEFORE importing Google GenAI libraries to ensure
proper authentication and region selection.

**Model Configuration**:
Uses `gemini-3-flash-preview` via Vertex AI. This model requires:
- GOOGLE_CLOUD_PROJECT: Set from settings (required)
- GOOGLE_CLOUD_LOCATION: Set from settings (default: us-central1 or global)
- Application Default Credentials (ADC) for authentication

**Usage**:
    >>> from agent.agent import root_agent
    >>> from google.adk.runners import Runner
    >>> runner = Runner(agent=root_agent, app_name="data_insights_agent")
    >>> # Run agent with user input
    >>> async for event in runner.run_async(user_id="user1", session_id="sess1", new_message=...):
    ...     process_event(event)

**Important**:
This module has side effects on import - it sets os.environ variables. Import
this module early in application startup before other Google libraries.
"""

import os
from google.adk.agents import Agent

from .callbacks import after_tool_callback, before_tool_callback
from .config import settings
from .prompts import SYSTEM_INSTRUCTION
from .tools import CUSTOM_TOOLS
from .enrichment import create_enrichment_agent, request_enrichment

# ========== Vertex AI Environment Configuration ==========
# These environment variables MUST be set before Google GenAI client initialization
# to ensure proper Vertex AI authentication and region selection.
#
# GOOGLE_GENAI_USE_VERTEXAI: Enables Vertex AI mode (vs direct Gemini API)
# GOOGLE_CLOUD_PROJECT: GCP project ID for Vertex AI billing and access control
# GOOGLE_CLOUD_LOCATION: Region for Vertex AI API calls (affects model availability)
#
# NOTE: These are set at module import time, which is a side effect. For production,
# consider setting these in the main application entry point before importing agents.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_region


def create_agent() -> Agent:
    """Create and configure the Data Insights Agent with enrichment capability.

    Initializes a Google ADK Agent with the following configuration:
    - Model: gemini-3-flash-preview (via Vertex AI)
    - Tools: BigQuery schema/query tools + calculated columns + enrichment request
    - Sub-agents: Enrichment agent (for Google Search-based data augmentation)
    - Instructions: SYSTEM_INSTRUCTION prompt (~250 lines of behavior rules)

    **Agent Architecture**:
    The agent uses a two-tier tool system:
    1. Main agent tools (CUSTOM_TOOLS + request_enrichment):
       - get_available_tables, get_table_schema (schema exploration)
       - validate_sql_query, execute_query_with_metadata (query execution)
       - add_calculated_column (derive values without re-running queries)
       - request_enrichment (trigger enrichment workflow)

    2. Enrichment sub-agent tools (invoked via request_enrichment):
       - GoogleSearchTool (search for real-time data)
       - apply_enrichment (merge search results into query data)

    **Workflow**:
    User query → Main agent generates SQL → Executes query → (Optional) Enrichment
    → (Optional) Calculations → Return structured results to frontend

    Returns:
        Agent: Configured Google ADK Agent instance ready for use with Runner.

    Examples:
        >>> # Create agent and run with ADK Runner
        >>> agent = create_agent()
        >>> runner = Runner(agent=agent, app_name="data_insights_agent")
        >>> async for event in runner.run_async(...):
        ...     handle_event(event)

        >>> # Access pre-created root agent
        >>> from agent.agent import root_agent
        >>> print(root_agent.name)
        "data_insights_agent"

    Notes:
        - This function is called once at module initialization to create root_agent
        - Vertex AI environment variables must be set before calling this function
        - Model requires Application Default Credentials (ADC) for authentication
        - Enrichment sub-agent is created independently and passed as sub_agents param

    See Also:
        - create_enrichment_agent(): Creates the enrichment sub-agent
        - SYSTEM_INSTRUCTION: Full prompt defining agent behavior
        - CUSTOM_TOOLS: List of main agent tools from agent.tools module
    """

    # Create the enrichment sub-agent
    # This agent handles Google Search operations and data merging
    enrichment_agent = create_enrichment_agent()

    # Create the main agent with Vertex AI model
    # The agent combines:
    # - CUSTOM_TOOLS: Core BigQuery and calculation tools
    # - request_enrichment: Gateway to enrichment sub-agent
    # - enrichment_agent: Sub-agent for Google Search-based enrichment
    agent = Agent(
        name="data_insights_agent",
        model="gemini-3-flash-preview",
        description=(
            "A data insights assistant that helps users analyze BigQuery data "
            "using natural language. Converts questions to SQL, executes queries, "
            "and provides actionable insights. Can enrich results with real-time "
            "data from Google Search when requested."
        ),
        instruction=SYSTEM_INSTRUCTION,
        tools=CUSTOM_TOOLS + [request_enrichment],
        sub_agents=[enrichment_agent],
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )

    return agent


# pylint: disable=pointless-string-statement
"""Global root agent instance for the Data Insights Agent application.

This is the primary agent used by the FastAPI application to handle all user
queries. It is initialized once at module import time and shared across all
requests within the same process.

**Usage**:
This agent instance is used by the ADK Runner in the /api/chat endpoint to
process natural language queries and generate responses.

**Lifecycle**:
- Created: At module import time (when agent.agent is first imported)
- Shared: Across all requests in the same process (module-level singleton)
- Not shared: Across multiple worker processes (each worker has its own instance)

**State Management**:
The agent itself is stateless - conversation history and context are managed by:
- ADK InMemorySessionService: Tracks agent conversation state
- SessionService: Tracks chat history and UI state

**Configuration**:
- Model: gemini-3-flash-preview (via Vertex AI)
- Project/Region: Loaded from environment variables via settings
- Tools: CUSTOM_TOOLS + request_enrichment (see create_agent() for full list)
- Sub-agents: Enrichment agent for Google Search integration

**Thread Safety**:
The Agent object itself is thread-safe (read-only after initialization), but:
- Tool state (_last_query_result, _schema_cache) is NOT thread-safe
- For production with concurrent requests, consider external caching/storage

**Example**:
    >>> from agent.agent import root_agent
    >>> from google.adk.runners import Runner
    >>> runner = Runner(agent=root_agent, app_name="data_insights_agent")
    >>> # Agent is ready to process requests
    >>> async for event in runner.run_async(user_id="user1", session_id="s1", new_message=msg):
    ...     process(event)

**Important**:
This global instance is initialized with environment variables from settings.
Ensure settings.google_cloud_project and settings.google_cloud_region are
configured correctly in .env before importing this module.

See Also:
    - create_agent(): Function that creates this instance
    - api.routes.chat(): Main endpoint that uses this agent
    - agent.tools: Module containing agent tools
"""
root_agent = create_agent()
