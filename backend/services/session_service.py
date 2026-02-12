"""Session management service for chat conversations."""

import uuid
from datetime import datetime
from typing import Optional
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event

from api.models import ChatMessage, MessageRole, SessionInfo


class SessionService:
    """Manages chat sessions and conversation history for the Data Insights Agent.

    This service provides session lifecycle management and message storage for chat
    conversations. It works alongside Google ADK's InMemorySessionService to maintain
    both conversation history (messages) and agent state (ADK internal state).

    **Architecture**:
    - SessionService (this class): Manages conversation history and metadata
    - ADK InMemorySessionService: Manages agent state and context
    - Session IDs are shared between both services (ADK sessions prefixed with "adk_")

    **Session Structure**:
    Each session stores:
    - id: Unique identifier (UUID)
    - name: Human-readable name (auto-generated or user-provided)
    - created_at: Creation timestamp
    - updated_at: Last modification timestamp
    - messages: List of ChatMessage objects (user and assistant turns)

    **CRITICAL LIMITATIONS**:

    1. **In-Memory Storage Only**:
       - All session data is stored in the `_sessions` dictionary (RAM)
       - Sessions are LOST when the server restarts
       - Not suitable for production without persistent storage
       - For production, replace with database (PostgreSQL, MongoDB) or cache (Redis)

    2. **NOT Thread-Safe**:
       - Dictionary operations are not atomic
       - Concurrent requests may cause race conditions
       - Multiple workers (gunicorn, uvicorn --workers) will have separate state
       - For production, use external session store or add locking (threading.Lock)

    3. **No Session Expiration**:
       - Sessions never expire automatically
       - Memory usage grows unbounded over time
       - Manual cleanup required or implement TTL-based expiration

    **Usage Pattern**:
    ```python
    # Create or get session
    session_id = session_service.get_or_create_session(request.session_id)

    # Add user message
    user_msg = session_service.add_message(session_id, MessageRole.USER, "Show sales by state")

    # Get conversation context for agent
    context = session_service.get_conversation_context(session_id)

    # Add assistant response
    assistant_msg = session_service.add_message(
        session_id,
        MessageRole.ASSISTANT,
        "Here are the sales...",
        query_result=result
    )
    ```

    Attributes:
        adk_session_service (InMemorySessionService): Google ADK's session service for agent state.
        _sessions (dict[str, dict]): In-memory storage of session metadata and messages.
    """

    def __init__(self):
        """Initialize the SessionService with in-memory storage.

        Creates empty session dictionary and initializes ADK's InMemorySessionService
        for agent state management.

        WARNING: All data is stored in memory and will be lost on server restart.
        """
        # Use ADK's built-in session service for agent state
        self.adk_session_service = InMemorySessionService()
        # Keep track of our own metadata (in-memory dictionary)
        self._sessions: dict[str, dict] = {}

    def create_session(self, name: Optional[str] = None) -> str:
        """Create a new chat session with a unique ID.

        Initializes a new session with metadata and an empty message list.
        Session ID is a UUID v4 for guaranteed uniqueness.

        Args:
            name (Optional[str]): Human-readable name for the session.
                If not provided, auto-generates "Session N" where N is the count.

        Returns:
            str: The newly created session ID (UUID format).

        Examples:
            >>> # Create named session
            >>> session_id = session_service.create_session(name="Sales Analysis")
            >>> session_id
            "550e8400-e29b-41d4-a716-446655440000"

            >>> # Create auto-named session
            >>> session_id = session_service.create_session()
            >>> session_service.get_session_info(session_id).name
            "Session 1"

        Notes:
            - Session is stored in-memory only (lost on restart)
            - No expiration is set (lives until server restart or manual deletion)
            - Thread-safety: Not thread-safe for concurrent creation
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        self._sessions[session_id] = {
            "id": session_id,
            "name": name or f"Session {len(self._sessions) + 1}",
            "created_at": now,
            "updated_at": now,
            "messages": []
        }

        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve a session by its ID.

        Args:
            session_id (str): The session ID to look up.

        Returns:
            Optional[dict]: The session dictionary if found, None otherwise.
                Session dict structure:
                {
                    "id": str,
                    "name": str,
                    "created_at": datetime,
                    "updated_at": datetime,
                    "messages": list[ChatMessage]
                }

        Examples:
            >>> session = session_service.get_session("550e8400-e29b-41d4-a716-446655440000")
            >>> if session:
            ...     print(session["name"])
            "Sales Analysis"

            >>> session = session_service.get_session("nonexistent")
            >>> session is None
            True

        Notes:
            - Returns raw session dict (not SessionInfo model)
            - For API responses, use get_session_info() instead
        """
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get an existing session or create a new one if not found.

        Convenience method for the common pattern of continuing existing sessions
        or starting new ones. Used by the /api/chat endpoint.

        Args:
            session_id (Optional[str]): Session ID to look up. If None or not found,
                creates a new session.

        Returns:
            str: Existing session ID if found, or newly created session ID.

        Examples:
            >>> # First request (no session)
            >>> session_id = session_service.get_or_create_session(None)
            >>> session_id
            "550e8400-e29b-41d4-a716-446655440000"

            >>> # Subsequent request (existing session)
            >>> same_id = session_service.get_or_create_session(session_id)
            >>> same_id == session_id
            True

            >>> # Invalid session ID (creates new)
            >>> new_id = session_service.get_or_create_session("invalid-id")
            >>> new_id != "invalid-id"
            True

        Notes:
            - Always returns a valid session ID
            - Safe to call with untrusted session IDs (creates new if invalid)
            - Used as the entry point for all chat requests
        """
        if session_id and session_id in self._sessions:
            return session_id
        return self.create_session()

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        **kwargs
    ) -> ChatMessage:
        """Add a message to a session's conversation history.

        Creates a new ChatMessage with a unique ID and appends it to the session's
        message list. Updates the session's updated_at timestamp.

        Args:
            session_id (str): The session ID to add the message to.
            role (MessageRole): Who sent the message (USER, ASSISTANT, or SYSTEM).
            content (str): The text content of the message.
            **kwargs: Additional fields to pass to ChatMessage constructor:
                - query_result (QueryResult): Query results from BigQuery
                - clarifying_question (ClarifyingQuestion): Question from agent
                - insights (list[Insight]): Proactive insights
                - is_streaming (bool): Whether message is streaming

        Returns:
            ChatMessage: The newly created message with generated ID and timestamp.

        Raises:
            ValueError: If the session_id does not exist.

        Examples:
            >>> # Add user message
            >>> msg = session_service.add_message(
            ...     session_id="550e8400-...",
            ...     role=MessageRole.USER,
            ...     content="Show me sales by state"
            ... )
            >>> msg.id
            "7c9e6679-..."

            >>> # Add assistant message with query result
            >>> msg = session_service.add_message(
            ...     session_id="550e8400-...",
            ...     role=MessageRole.ASSISTANT,
            ...     content="Here are the sales by state:",
            ...     query_result=QueryResult(...)
            ... )
            >>> msg.query_result.total_rows
            50

        Notes:
            - Message IDs are UUID v4 for uniqueness
            - Messages are stored in chronological order
            - Session's updated_at is automatically updated
            - Thread-safety: Not thread-safe for concurrent message additions
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        message = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            **kwargs
        )

        session["messages"].append(message)
        session["updated_at"] = datetime.utcnow()

        return message

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        """Get all messages for a session in chronological order.

        Retrieves the complete conversation history for a session.

        Args:
            session_id (str): The session ID to get messages for.

        Returns:
            list[ChatMessage]: List of messages in chronological order (oldest first).
                Returns empty list if session doesn't exist.

        Examples:
            >>> messages = session_service.get_messages("550e8400-...")
            >>> len(messages)
            10
            >>> messages[0].role
            MessageRole.USER
            >>> messages[1].role
            MessageRole.ASSISTANT

        Notes:
            - Messages include full ChatMessage objects with all metadata
            - Does not raise error for missing sessions (returns empty list)
            - For conversation context formatting, use get_conversation_context()
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session["messages"]

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Get session metadata as a SessionInfo model (for API responses).

        Converts internal session dict to the SessionInfo Pydantic model,
        which includes computed fields like message_count.

        Args:
            session_id (str): The session ID to get info for.

        Returns:
            Optional[SessionInfo]: Session metadata model if found, None otherwise.
                SessionInfo includes:
                - id: Session ID
                - name: Session name
                - created_at: Creation timestamp
                - updated_at: Last modification timestamp
                - message_count: Number of messages in the conversation

        Examples:
            >>> info = session_service.get_session_info("550e8400-...")
            >>> info.name
            "Sales Analysis"
            >>> info.message_count
            10
            >>> info.created_at
            datetime.datetime(2024, 1, 15, 10, 30, 0)

        Notes:
            - Returns Pydantic model (suitable for API responses)
            - For raw session dict, use get_session() instead
            - Does not include full message objects (use get_messages() for that)
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        return SessionInfo(
            id=session["id"],
            name=session["name"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            message_count=len(session["messages"])
        )

    def list_sessions(self) -> list[SessionInfo]:
        """List all active sessions with metadata.

        Returns metadata for all sessions currently in memory, sorted by
        session ID (which is chronologically ordered due to UUID structure).

        Returns:
            list[SessionInfo]: List of session metadata models.

        Examples:
            >>> sessions = session_service.list_sessions()
            >>> len(sessions)
            5
            >>> sessions[0].name
            "Sales Analysis"
            >>> sessions[0].message_count
            12

        Notes:
            - Returns all sessions (no pagination)
            - Memory usage grows with number of sessions (no cleanup)
            - For production, implement pagination and filtering
        """
        return [
            SessionInfo(
                id=s["id"],
                name=s["name"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=len(s["messages"])
            )
            for s in self._sessions.values()
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages.

        Permanently removes the session from in-memory storage. This action
        cannot be undone.

        Args:
            session_id (str): The session ID to delete.

        Returns:
            bool: True if session was found and deleted, False if not found.

        Examples:
            >>> # Delete existing session
            >>> success = session_service.delete_session("550e8400-...")
            >>> success
            True

            >>> # Try to delete non-existent session
            >>> success = session_service.delete_session("nonexistent")
            >>> success
            False

        Notes:
            - Deletion is immediate and permanent (in-memory storage)
            - Does not delete ADK session state (only local conversation history)
            - For production, consider soft deletion with archival
            - Thread-safety: Not thread-safe for concurrent deletions
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_conversation_context(self, session_id: str, max_messages: int = 10) -> str:
        """Get recent conversation history as formatted text for agent context.

        Formats the last N messages as a plain text summary that can be prepended
        to the current user message to provide the agent with conversation context.
        This helps the agent understand references to previous queries and maintain
        continuity.

        Args:
            session_id (str): The session ID to get context for.
            max_messages (int, optional): Maximum number of recent messages to include.
                Defaults to 10. Limits context size to avoid token limits.

        Returns:
            str: Formatted conversation history as newline-separated "Role: content" pairs.
                Returns empty string if session doesn't exist or has no messages.

        Examples:
            >>> context = session_service.get_conversation_context("550e8400-...", max_messages=3)
            >>> print(context)
            User: Show me sales by state
            Assistant: Here are the sales by state: ...
            User: What about Texas specifically?

            >>> # Use in chat request
            >>> full_prompt = f"Previous conversation:\\n{context}\\n\\nCurrent question: {user_message}"

        Notes:
            - Only includes text content (no query results or metadata)
            - Older messages are truncated if conversation exceeds max_messages
            - Format is optimized for LLM context understanding
            - Default limit of 10 prevents excessive token usage
        """
        messages = self.get_messages(session_id)
        recent = messages[-max_messages:] if len(messages) > max_messages else messages

        context_parts = []
        for msg in recent:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            context_parts.append(f"{role}: {msg.content}")

        return "\n".join(context_parts)


"""Global session service instance (singleton pattern).

This is the main entry point for session management throughout the application.
Import and use this instance in API routes and other services.

**WARNING**: This is a module-level singleton with in-memory storage.
- State is shared across all requests in the same process
- State is NOT shared across multiple worker processes
- State is lost on server restart

For production deployment with multiple workers, consider:
- External session store (Redis, PostgreSQL)
- Sticky sessions (route users to same worker)
- Database-backed session storage

Example:
    >>> from services.session_service import session_service
    >>> session_id = session_service.create_session(name="Analysis")
    >>> session_service.add_message(session_id, MessageRole.USER, "Hello")
"""
session_service = SessionService()
