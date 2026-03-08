"""WebSocket handler for streaming chat responses."""

import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from google.adk.runners import Runner
from google.genai import types

from agent.agent import root_agent
from services.session_service import session_service
from .models import MessageRole, StreamEvent


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_event(self, session_id: str, event: StreamEvent):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(event.model_dump(mode='json'))


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, session_id: str):
    """
    Handle WebSocket connection for streaming chat.

    Protocol:
    - Client sends: {"message": "user query"}
    - Server sends: StreamEvent objects with different event_types:
        - "start": Indicates processing has started
        - "token": Partial text response
        - "query_start": SQL query execution started
        - "query_result": Query results available
        - "insight": Proactive insight generated
        - "done": Response complete
        - "error": An error occurred
    """
    await manager.connect(websocket, session_id)

    # Ensure session exists
    session_service.get_or_create_session(session_id)

    try:
        while True:
            # Wait for message from client
            data = await websocket.receive_json()
            message = data.get("message", "")

            if not message:
                continue

            # Add user message to session
            session_service.add_message(
                session_id=session_id,
                role=MessageRole.USER,
                content=message,
            )

            # Send start event
            await manager.send_event(
                session_id,
                StreamEvent(event_type="start", data={"message": "Processing your request..."})
            )

            try:
                # Create runner for streaming
                runner = Runner(
                    agent=root_agent,
                    app_name="data_insights_agent",
                    session_service=session_service.adk_session_service,
                )

                # Get conversation context
                context = session_service.get_conversation_context(session_id, max_messages=5)

                full_prompt = message
                if context:
                    full_prompt = f"Previous conversation:\n{context}\n\nCurrent question: {message}"

                response_text = ""
                query_result = None

                # Stream the response
                async for event in runner.run_async(
                    user_id="default_user",
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=full_prompt)]
                    ),
                ):
                    # Handle text content
                    if hasattr(event, 'content') and event.content:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                response_text += part.text
                                await manager.send_event(
                                    session_id,
                                    StreamEvent(event_type="token", data={"text": part.text})
                                )

                    # Handle tool calls (query execution)
                    if hasattr(event, 'tool_calls') and event.tool_calls:
                        for tool_call in event.tool_calls:
                            if 'execute' in str(tool_call).lower() or 'query' in str(tool_call).lower():
                                await manager.send_event(
                                    session_id,
                                    StreamEvent(event_type="query_start", data={"message": "Executing query..."})
                                )

                    # Handle tool results
                    if hasattr(event, 'tool_results'):
                        for tool_result in event.tool_results:
                            if isinstance(tool_result, dict) and tool_result.get("status") == "success":
                                if "rows" in tool_result:
                                    query_result = {
                                        "columns": tool_result.get("columns", []),
                                        "rows": tool_result.get("rows", []),
                                        "total_rows": tool_result.get("total_rows", 0),
                                        "query_time_ms": tool_result.get("query_time_ms", 0),
                                        "sql": tool_result.get("sql", ""),
                                    }
                                    await manager.send_event(
                                        session_id,
                                        StreamEvent(event_type="query_result", data=query_result)
                                    )

                # Add assistant message to session
                session_service.add_message(
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=response_text or "I couldn't generate a response.",
                )

                # Send completion event
                await manager.send_event(
                    session_id,
                    StreamEvent(
                        event_type="done",
                        data={
                            "message": response_text,
                            "query_result": query_result,
                        }
                    )
                )

            except Exception as e:
                import traceback
                traceback.print_exc()

                await manager.send_event(
                    session_id,
                    StreamEvent(event_type="error", data={"error": str(e)})
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
