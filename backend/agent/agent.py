"""Data Insights Agent - Main agent definition using Google ADK."""

import os
from google.adk.agents import Agent

from .config import settings
from .prompts import SYSTEM_INSTRUCTION
from .tools import CUSTOM_TOOLS
from .enrichment_agent import create_enrichment_agent
from .enrichment_tools import request_enrichment

# Set environment variables for Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_region


def create_agent() -> Agent:
    """Create and configure the Data Insights Agent with enrichment capability."""

    # Create the enrichment sub-agent
    enrichment_agent = create_enrichment_agent()

    # Create the main agent with Vertex AI model
    # Include request_enrichment tool and enrichment sub-agent
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
    )

    return agent


# Create the root agent instance for ADK
root_agent = create_agent()
