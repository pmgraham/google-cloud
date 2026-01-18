"""API routes for the Data Insights Agent."""

import json
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.agent import root_agent

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
    Insight,
    ClarifyingQuestion,
)

router = APIRouter()


def parse_agent_response(response_text: str) -> dict:
    """
    Parse the agent's response to extract structured data.
    Returns a dict with: summary, query_result, insights, clarifying_question
    """
    result = {
        "summary": response_text,
        "query_result": None,
        "insights": [],
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

    # Look for insight patterns
    insight_patterns = [
        (r"I notice[d]? that (.+?)(?:\.|$)", "trend"),
        (r"Note: (.+?)(?:\.|$)", "anomaly"),
        (r"For context,? (.+?)(?:\.|$)", "comparison"),
        (r"You might (?:also )?(?:find it useful|be interested|want) to (.+?)(?:\.|$)", "suggestion"),
    ]

    for pattern, insight_type in insight_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        for match in matches:
            result["insights"].append(
                Insight(type=insight_type, message=match.strip())
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
    """
    Send a message to the agent and get a response.
    This is the main chat endpoint.
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
            # Session doesn't exist, create it
            print(f"Creating new ADK session: {adk_session_id}")
            await _adk_session_service.create_session(
                app_name="data_insights_agent",
                user_id="default_user",
                session_id=adk_session_id,
            )
        else:
            print(f"Using existing ADK session: {adk_session_id}")

        # Run the agent
        response_parts = []
        query_result = None

        async for event in runner.run_async(
            user_id="default_user",
            session_id=adk_session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=full_prompt)]
            ),
        ):
            # Collect response parts from content
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_parts.append(part.text)

            # Check for function responses using the method
            if hasattr(event, 'get_function_responses'):
                func_responses = event.get_function_responses()
                if func_responses:
                    for func_response in func_responses:
                        print(f"Function response found: {func_response.name if hasattr(func_response, 'name') else 'unknown'}")
                        # Extract the response data
                        if hasattr(func_response, 'response'):
                            result_data = func_response.response
                            print(f"Response data type: {type(result_data)}, keys: {result_data.keys() if isinstance(result_data, dict) else 'N/A'}")
                            if isinstance(result_data, dict) and result_data.get("status") == "success" and "rows" in result_data:
                                query_result = QueryResult(
                                    columns=[ColumnInfo(**col) for col in result_data.get("columns", [])],
                                    rows=result_data.get("rows", []),
                                    total_rows=result_data.get("total_rows", 0),
                                    query_time_ms=result_data.get("query_time_ms", 0),
                                    sql=result_data.get("sql", ""),
                                )
                                print(f"Captured query result with {query_result.total_rows} rows")

        # Combine response
        response_text = "\n".join(response_parts) if response_parts else "I apologize, but I couldn't generate a response. Please try rephrasing your question."

        # Parse the response for structured data
        parsed = parse_agent_response(response_text)

        # Create assistant message
        assistant_message = session_service.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            query_result=query_result,
            insights=parsed["insights"],
            clarifying_question=parsed["clarifying_question"],
        )

        # Get conversation history
        history = session_service.get_messages(session_id)

        return ChatResponse(
            session_id=session_id,
            message=assistant_message,
            conversation_history=history,
        )

    except Exception as e:
        # Log the error and return a friendly message
        import traceback
        traceback.print_exc()

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
