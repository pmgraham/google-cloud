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
    """Information about a data column."""
    name: str
    type: str
    is_enriched: bool = False
    is_calculated: bool = False


class EnrichmentMetadata(BaseModel):
    """Metadata about enrichment applied to query results."""
    source_column: str
    enriched_fields: list[str]
    total_enriched: int
    warnings: list[str] = Field(default_factory=list)
    partial_failure: bool = False


class CalculatedColumnInfo(BaseModel):
    """Information about a calculated column."""
    name: str
    expression: str
    format_type: str = "number"


class CalculationMetadata(BaseModel):
    """Metadata about calculations applied to query results."""
    calculated_columns: list[CalculatedColumnInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    """Results from a SQL query execution."""
    columns: list[ColumnInfo]
    rows: list[dict[str, Any]]
    total_rows: int
    query_time_ms: float
    sql: str
    enrichment_metadata: Optional[EnrichmentMetadata] = None
    calculation_metadata: Optional[CalculationMetadata] = None


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
    """A message in the chat conversation."""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    query_result: Optional[QueryResult] = None
    clarifying_question: Optional[ClarifyingQuestion] = None
    insights: list[Insight] = Field(default_factory=list)
    is_streaming: bool = False


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the agent."""
    session_id: str
    message: ChatMessage
    conversation_history: list[ChatMessage] = Field(default_factory=list)


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
