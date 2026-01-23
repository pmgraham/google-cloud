"""API routes for the Data Insights Agent."""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Maximum time (seconds) the agent is allowed to process a single chat request
# before the endpoint returns a timeout error to the client.
_AGENT_TIMEOUT_SECONDS = 120

from agent.agent import root_agent
from agent.tools import get_and_clear_pending_insights
from .observability import AgentRunTracer

# Global ADK session service for managing agent sessions
_adk_session_service = InMemorySessionService()
from agent.config import settings
from services.session_service import session_service
from .models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    MessageRole,
    SessionCreateRequest,
    SessionInfo,
    SessionListResponse,
    HealthResponse,
    ErrorResponse,
    QueryResult,
    ColumnInfo,
    EnrichmentMetadata,
    CalculationMetadata,
    Insight,
    ClarifyingQuestion,
)

router = APIRouter()


def parse_agent_response(response_text: str) -> dict:
    """Parse the agent's text response to extract structured components.

    Currently extracts clarifying questions from the agent's text. Insights
    are no longer extracted here — they arrive as structured data via the
    report_insight tool and are collected from _pending_insights after the
    event stream completes.

    Args:
        response_text (str): The raw text response from the AI agent.

    Returns:
        dict: Structured data extracted from the response:
            {
                "summary": str,
                "query_result": None,
                "clarifying_question": ClarifyingQuestion | None
            }
    """
    result = {
        "summary": response_text,
        "query_result": None,
        "clarifying_question": None,
    }

    # Check for clarifying questions (look for question marks with options)
    # Extract just the question sentence, not everything before it
    question_pattern = r"((?:Which|What|Do you|Would you|Should I|Could you|How would)[^?]*\?)"
    question_match = re.search(question_pattern, response_text, re.IGNORECASE)
    if question_match:
        # Look for bullet points or numbered options
        options_pattern = r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s*(.+?)(?=\n|$)"
        options = re.findall(options_pattern, response_text)
        if options:
            result["clarifying_question"] = ClarifyingQuestion(
                question=question_match.group(1).strip(),  # Just the question sentence
                options=[opt.strip() for opt in options[:5]],  # Max 5 options
            )

    return result


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
    )


@router.post("/sessions", response_model=SessionInfo)
async def create_session(request: SessionCreateRequest):
    """Create a new chat session."""
    session_id = session_service.create_session(name=request.name)
    session_info = session_service.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=500, detail="Failed to create session")
    return session_info


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """List all chat sessions."""
    sessions = session_service.list_sessions()
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session information."""
    session_info = session_service.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_info


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    if not session_service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessage])
async def get_messages(session_id: str):
    """Get all messages for a session."""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_service.get_messages(session_id)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the AI agent and receive a structured response with query results.

    This is the **main chat endpoint** for natural language data analysis. It:
    1. Manages conversation sessions for context preservation
    2. Routes messages to the Google ADK agent (gemini-3-flash-preview)
    3. Processes agent responses including tool calls (BigQuery queries, enrichment)
    4. Extracts structured data from the event stream
    5. Parses text for insights and clarifying questions
    6. Returns the assistant's response with full conversation history

    **Event Stream Processing**:
    The agent runs asynchronously and emits events during execution:
    - `content` events: Text response parts (collected and joined)
    - `function_response` events: Tool execution results (e.g., execute_query_with_metadata)

    QueryResult objects are extracted from function_response events when the response
    contains {"status": "success", "rows": [...]}. This captures results from:
    - execute_query_with_metadata() - Base query results
    - apply_enrichment() - Results with enriched columns added
    - add_calculated_column() - Results with calculated columns added

    **Session Management**:
    - Sessions use InMemorySessionService (ADK) for agent state
    - Session IDs are prefixed with "adk_" for ADK sessions
    - Session service tracks conversation history and context
    - If session_id is not provided, a new session is created

    **Context Handling**:
    Previous conversation context is prepended to the current message to help
    the agent maintain continuity and understand references to prior queries.

    Args:
        request (ChatRequest): User message and optional session ID.

    Returns:
        ChatResponse: The agent's response including:
            - session_id: Session ID for this conversation
            - message: The assistant's message (may include query_result)
            - conversation_history: Full chat history

    Raises:
        HTTPException: Not raised directly, but errors are caught and returned
            as assistant messages with error text.

    Examples:
        >>> # Simple query
        >>> response = await chat(ChatRequest(message="Show me sales by state"))
        >>> response.message.query_result.total_rows
        50
        >>> response.message.content
        "Here are the sales by state..."

        >>> # Continue conversation
        >>> response = await chat(ChatRequest(
        ...     message="What about Texas?",
        ...     session_id=response.session_id
        ... ))

        >>> # Error handling
        >>> response = await chat(ChatRequest(message="invalid query"))
        >>> "error" in response.message.content.lower()
        True

    Notes:
        - Agent tool calls (BigQuery, enrichment, calculations) happen inside the ADK event loop
        - Only the final aggregated results are returned to the client
        - Streaming is not yet implemented (is_streaming always False)
        - Session state is lost on server restart (in-memory storage)
    """
    # Get or create session in our service
    session_id = session_service.get_or_create_session(request.session_id)

    # Add user message to session
    user_message = session_service.add_message(
        session_id=session_id,
        role=MessageRole.USER,
        content=request.message,
    )

    try:
        # Create runner for the agent with session service
        runner = Runner(
            agent=root_agent,
            app_name="data_insights_agent",
            session_service=_adk_session_service,
        )

        # Get conversation context from our session
        context = session_service.get_conversation_context(session_id)

        # Build the prompt with context
        full_prompt = request.message
        if context:
            full_prompt = f"Previous conversation:\n{context}\n\nCurrent question: {request.message}"

        # Create ADK session if it doesn't exist
        adk_session_id = f"adk_{session_id}"
        existing_session = await _adk_session_service.get_session(
            app_name="data_insights_agent",
            user_id="default_user",
            session_id=adk_session_id,
        )
        if existing_session is None:
            await _adk_session_service.create_session(
                app_name="data_insights_agent",
                user_id="default_user",
                session_id=adk_session_id,
            )

        # ========== ADK Event Stream Processing ==========
        # Wrapped in a nested coroutine so asyncio.wait_for can enforce a
        # timeout — without this, a looping or stuck agent hangs the endpoint.
        tracer = AgentRunTracer(session_id=session_id, prompt=request.message)
        response_parts = []
        query_result = None

        async def _drain_agent_events():
            """Consume all events from the ADK runner."""
            nonlocal query_result

            async for event in runner.run_async(
                user_id="default_user",
                session_id=adk_session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=full_prompt)]
                ),
            ):
                _author = getattr(event, 'author', '?')

                # Extract tool call names for the tracer decision trace
                _tool_names = None
                if hasattr(event, 'get_function_calls'):
                    _fc = event.get_function_calls()
                    if _fc:
                        _tool_names = [
                            fc.name for fc in _fc if hasattr(fc, 'name')
                        ]

                tracer.record_event(author=_author, tool_calls=_tool_names)

                # Collect text response parts
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_parts.append(part.text)

                # Extract QueryResult from function responses
                if hasattr(event, 'get_function_responses'):
                    func_responses = event.get_function_responses()
                    if func_responses:
                        for func_response in func_responses:
                            if not hasattr(func_response, 'response'):
                                continue
                            result_data = func_response.response
                            if (
                                isinstance(result_data, dict)
                                and result_data.get("status") == "success"
                                and "rows" in result_data
                            ):
                                enrichment_meta = None
                                if result_data.get("enrichment_metadata"):
                                    enrichment_meta = EnrichmentMetadata(
                                        **result_data["enrichment_metadata"]
                                    )
                                calc_meta = None
                                if result_data.get("calculation_metadata"):
                                    calc_meta = CalculationMetadata(
                                        **result_data["calculation_metadata"]
                                    )
                                query_result = QueryResult(
                                    columns=[
                                        ColumnInfo(**col)
                                        for col in result_data.get("columns", [])
                                    ],
                                    rows=result_data.get("rows", []),
                                    total_rows=result_data.get("total_rows", 0),
                                    query_time_ms=result_data.get("query_time_ms", 0),
                                    sql=result_data.get("sql", ""),
                                    enrichment_metadata=enrichment_meta,
                                    calculation_metadata=calc_meta,
                                )

        # ========== Enforce timeout on the agent event loop ==========
        try:
            await asyncio.wait_for(
                _drain_agent_events(),
                timeout=_AGENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            outcome = tracer.complete(timed_out=True)

            error_message = session_service.add_message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=(
                    "I'm sorry. I hit a snag on my end while thinking about "
                    "your prompt: AGENT_TIMEOUT  Could you try again?"
                ),
            )
            return ChatResponse(
                session_id=session_id,
                message=error_message,
                conversation_history=session_service.get_messages(session_id),
            )

        # Combine response
        response_text = "\n".join(response_parts) if response_parts else ""

        # Emit the structured run log (summary, decision trace, outcome)
        outcome = tracer.complete(response_text=response_text)

        if not response_text:
            response_text = (
                "I apologize, but I couldn't generate a response. "
                "Please try rephrasing your question."
            )

        # Collect insights reported via the report_insight tool
        raw_insights = get_and_clear_pending_insights()
        insights = [
            Insight(type=ins["type"], message=ins["message"])
            for ins in raw_insights
        ]

        # Parse the response for clarifying questions
        parsed = parse_agent_response(response_text)

        # Create assistant message
        assistant_message = session_service.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            query_result=query_result,
            insights=insights,
            clarifying_question=parsed["clarifying_question"],
        )

        return ChatResponse(
            session_id=session_id,
            message=assistant_message,
            conversation_history=session_service.get_messages(session_id),
        )

    except Exception as e:
        # Emit structured log for the error case
        if 'tracer' in locals():
            tracer.complete(error=e)

        error_message = session_service.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=f"I encountered an error processing your request: {str(e)}. Please try again.",
        )

        return ChatResponse(
            session_id=session_id,
            message=error_message,
            conversation_history=session_service.get_messages(session_id),
        )


@router.get("/schema/tables")
async def get_tables():
    """Get available BigQuery tables and their schemas."""
    from agent.tools import get_available_tables
    return get_available_tables()


@router.get("/schema/tables/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    from agent.tools import get_table_schema
    return get_table_schema(table_name)
