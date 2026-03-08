"""Pydantic models for API request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a message in the conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChartType(str, Enum):
    """Available chart types for visualization."""
    TABLE = "table"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"


class ColumnInfo(BaseModel):
    """Information about a data column in query results.

    Used in QueryResult to describe the schema of returned data, including
    metadata flags for enriched and calculated columns.
    """
    name: str = Field(
        ...,
        description="Column name as it appears in the data (e.g., 'state', '_enriched_capital')",
        examples=["state", "population", "_enriched_capital", "residents_per_store"]
    )
    type: str = Field(
        ...,
        description="BigQuery or inferred data type (STRING, INTEGER, FLOAT64, BOOLEAN, etc.)",
        examples=["STRING", "INTEGER", "FLOAT64"]
    )
    is_enriched: bool = Field(
        default=False,
        description="True if this column was added via apply_enrichment(). Enriched columns are prefixed with '_enriched_'."
    )
    is_calculated: bool = Field(
        default=False,
        description="True if this column was added via add_calculated_column(). Contains derived values from expressions."
    )


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment applied to query results via apply_enrichment().

    Tracks which column was enriched, what fields were added, success metrics,
    and any warnings about missing or failed enrichments. This metadata helps
    the frontend display enrichment badges and warnings.

    Enrichment adds real-time data from Google Search to query results without
    re-running the database query.
    """
    source_column: str = Field(
        ...,
        description="The column name that was enriched (e.g., 'state', 'city', 'company')",
        examples=["state", "city", "company_name"]
    )
    enriched_fields: list[str] = Field(
        ...,
        description="List of field names that were added via enrichment (without '_enriched_' prefix)",
        examples=[["capital", "population"], ["CEO", "founded_year"]]
    )
    total_enriched: int = Field(
        ...,
        description="Number of unique values that were successfully enriched",
        examples=[50, 15]
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of warnings about failed or missing enrichments (limited to first 5)",
        examples=[["No enrichment data found for 'PR'", "Field 'governor' not found"]]
    )
    partial_failure: bool = Field(
        default=False,
        description="True if any enrichments failed. Check warnings array for details."
    )


class CalculatedColumnInfo(BaseModel):
    """Information about a single calculated column added via add_calculated_column().

    Describes the expression and formatting used to create a derived column
    from existing query data.
    """
    name: str = Field(
        ...,
        description="Name of the calculated column",
        examples=["residents_per_store", "profit_margin", "growth_rate"]
    )
    expression: str = Field(
        ...,
        description="Mathematical expression used to calculate values (can reference other columns)",
        examples=["population / store_count", "revenue - costs", "_enriched_gdp / population"]
    )
    format_type: str = Field(
        default="number",
        description="Display format hint for frontend rendering",
        examples=["number", "integer", "percent", "currency"]
    )


class CalculationMetadata(BaseModel):
    """Metadata about calculations applied to query results via add_calculated_column().

    Tracks all calculated columns that were added, their expressions, and any
    warnings about calculation errors (e.g., division by zero, invalid expressions).

    Calculated columns allow deriving new values from existing data without
    re-running the database query, especially useful for combining base data
    with enriched data.
    """
    calculated_columns: list[CalculatedColumnInfo] = Field(
        default_factory=list,
        description="List of calculated columns that were added to the result"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of calculation errors or warnings (limited to first 5 rows)",
        examples=[["Row 3: Division by zero", "Row 7: Invalid expression"]]
    )


class QueryResult(BaseModel):
    """Results from a SQL query execution with optional enrichment and calculation metadata.

    This is the primary data structure returned from BigQuery queries via
    execute_query_with_metadata(). It can be augmented with enriched columns
    (from Google Search) and calculated columns (from expressions) without
    re-running the database query.

    The frontend uses this structure to render data tables, charts, and
    display enrichment/calculation metadata badges.
    """
    columns: list[ColumnInfo] = Field(
        ...,
        description="Schema information for all columns in the result, including enriched and calculated columns"
    )
    rows: list[dict[str, Any]] = Field(
        ...,
        description=(
            "Array of data rows, where each row is a dictionary mapping column names to values. "
            "Normal values are primitives (str, int, float). "
            "Enriched values are objects: {value, source, confidence, freshness, warning}. "
            "Calculated values are objects: {value, expression, format_type, is_calculated, warning}."
        ),
        examples=[[
            {"state": "CA", "population": 39500000},
            {"state": "TX", "population": 29100000}
        ]]
    )
    total_rows: int = Field(
        ...,
        description="Total number of rows returned (may be less than full query result if LIMIT was applied)",
        examples=[50, 1000]
    )
    query_time_ms: float = Field(
        ...,
        description="Query execution time in milliseconds (from BigQuery)",
        examples=[234.56, 1250.75]
    )
    sql: str = Field(
        ...,
        description="The actual SQL query that was executed (may include auto-added LIMIT clause)",
        examples=["SELECT state, COUNT(*) as count FROM sales GROUP BY state LIMIT 1000"]
    )
    enrichment_metadata: Optional[EnrichmentMetadata] = Field(
        default=None,
        description="Present if apply_enrichment() was called. Contains info about enriched columns."
    )
    calculation_metadata: Optional[CalculationMetadata] = Field(
        default=None,
        description="Present if add_calculated_column() was called. Contains info about calculated columns."
    )


class ClarifyingQuestion(BaseModel):
    """A clarifying question from the agent."""
    question: str
    options: list[str] = Field(default_factory=list)
    context: Optional[str] = None


class Insight(BaseModel):
    """A proactive insight from the agent."""
    type: str  # trend, anomaly, comparison, suggestion
    message: str
    importance: str = "medium"  # low, medium, high


class ChatMessage(BaseModel):
    """A message in the chat conversation between user and AI agent.

    Represents a single turn in the conversation, which can include text,
    query results, insights, and clarifying questions from the agent.
    """
    id: str = Field(
        ...,
        description="Unique identifier for this message",
        examples=["msg_abc123"]
    )
    role: MessageRole = Field(
        ...,
        description="Who sent this message: 'user', 'assistant', or 'system'"
    )
    content: str = Field(
        ...,
        description="The text content of the message",
        examples=["Show me sales by state", "Here are the top 10 states by sales:"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this message was created (UTC)"
    )
    query_result: Optional[QueryResult] = Field(
        default=None,
        description="Present if this message contains query results from BigQuery"
    )
    clarifying_question: Optional[ClarifyingQuestion] = Field(
        default=None,
        description="Present if the agent is asking a clarifying question"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="Proactive insights generated by the agent (trends, anomalies, suggestions)"
    )
    is_streaming: bool = Field(
        default=False,
        description="True if this message is being streamed token-by-token (future feature)"
    )


class ChatRequest(BaseModel):
    """Request to send a message to the AI agent.

    The main API input for chat interactions. Session ID is optional;
    if not provided, a new session will be created.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's question or command in natural language",
        examples=["Show me sales by state", "What were the top 10 products last month?"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID to continue an existing conversation. If null, creates a new session."
    )


class ChatResponse(BaseModel):
    """Response from the AI agent containing the assistant's reply and conversation context.

    Includes the full conversation history to help the frontend maintain state.
    """
    session_id: str = Field(
        ...,
        description="Session ID for this conversation (use in subsequent requests to maintain context)"
    )
    message: ChatMessage = Field(
        ...,
        description="The assistant's response message (may include query results, insights, etc.)"
    )
    conversation_history: list[ChatMessage] = Field(
        default_factory=list,
        description="Full conversation history for this session, ordered chronologically"
    )


class SessionCreateRequest(BaseModel):
    """Request to create a new chat session."""
    name: Optional[str] = None


class SessionInfo(BaseModel):
    """Information about a chat session."""
    id: str
    name: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int


class SessionListResponse(BaseModel):
    """Response containing list of sessions."""
    sessions: list[SessionInfo]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StreamEvent(BaseModel):
    """Event sent during streaming response."""
    event_type: str  # "token", "query_start", "query_result", "insight", "done", "error"
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
