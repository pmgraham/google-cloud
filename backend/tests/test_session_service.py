"""Tests for services.session_service.SessionService."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from api.models import MessageRole
from services.session_service import SESSION_TTL, MAX_SESSIONS


# ---------- create_session ----------


class TestCreateSession:
    def test_auto_name(self, session_service):
        sid = session_service.create_session()
        info = session_service.get_session_info(sid)
        assert info.name == "Session 1"

    def test_custom_name(self, session_service):
        sid = session_service.create_session(name="Sales Q1")
        info = session_service.get_session_info(sid)
        assert info.name == "Sales Q1"

    def test_returns_uuid(self, session_service):
        sid = session_service.create_session()
        # UUID4 format: 8-4-4-4-12 hex chars
        assert len(sid.split("-")) == 5

    def test_increments_auto_name(self, session_service):
        session_service.create_session()
        sid2 = session_service.create_session()
        info2 = session_service.get_session_info(sid2)
        assert info2.name == "Session 2"


# ---------- get_session ----------


class TestGetSession:
    def test_found(self, session_service):
        sid = session_service.create_session()
        session = session_service.get_session(sid)
        assert session is not None
        assert session["id"] == sid

    def test_not_found(self, session_service):
        assert session_service.get_session("nonexistent") is None


# ---------- get_or_create_session ----------


class TestGetOrCreateSession:
    def test_existing(self, session_service):
        sid = session_service.create_session()
        returned = session_service.get_or_create_session(sid)
        assert returned == sid

    def test_invalid_id_creates_new(self, session_service):
        returned = session_service.get_or_create_session("bogus-id")
        assert returned != "bogus-id"
        assert session_service.get_session(returned) is not None

    def test_none_creates_new(self, session_service):
        returned = session_service.get_or_create_session(None)
        assert session_service.get_session(returned) is not None


# ---------- add_message ----------


class TestAddMessage:
    def test_user_message(self, session_service):
        sid = session_service.create_session()
        msg = session_service.add_message(sid, MessageRole.USER, "hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "hello"

    def test_assistant_message(self, session_service):
        sid = session_service.create_session()
        msg = session_service.add_message(sid, MessageRole.ASSISTANT, "hi there")
        assert msg.role == MessageRole.ASSISTANT

    def test_updates_timestamp(self, session_service):
        sid = session_service.create_session()
        session_before = session_service.get_session(sid)
        ts_before = session_before["updated_at"]
        time.sleep(0.01)
        session_service.add_message(sid, MessageRole.USER, "yo")
        session_after = session_service.get_session(sid)
        assert session_after["updated_at"] >= ts_before

    def test_raises_on_bad_session(self, session_service):
        with pytest.raises(ValueError, match="not found"):
            session_service.add_message("no-such-session", MessageRole.USER, "oops")


# ---------- get_messages ----------


class TestGetMessages:
    def test_empty(self, session_service):
        sid = session_service.create_session()
        assert session_service.get_messages(sid) == []

    def test_multiple_chronological(self, session_service):
        sid = session_service.create_session()
        session_service.add_message(sid, MessageRole.USER, "first")
        session_service.add_message(sid, MessageRole.ASSISTANT, "second")
        session_service.add_message(sid, MessageRole.USER, "third")
        msgs = session_service.get_messages(sid)
        assert len(msgs) == 3
        assert msgs[0].content == "first"
        assert msgs[2].content == "third"

    def test_missing_session_returns_empty(self, session_service):
        assert session_service.get_messages("ghost") == []


# ---------- delete_session ----------


class TestDeleteSession:
    def test_exists(self, session_service):
        sid = session_service.create_session()
        assert session_service.delete_session(sid) is True
        assert session_service.get_session(sid) is None

    def test_not_exists(self, session_service):
        assert session_service.delete_session("nope") is False


# ---------- get_conversation_context ----------


class TestGetConversationContext:
    def test_formatting(self, session_service):
        sid = session_service.create_session()
        session_service.add_message(sid, MessageRole.USER, "Show sales")
        session_service.add_message(sid, MessageRole.ASSISTANT, "Here are the results")
        ctx = session_service.get_conversation_context(sid)
        assert "User: Show sales" in ctx
        assert "Assistant: Here are the results" in ctx

    def test_max_messages_truncation(self, session_service):
        sid = session_service.create_session()
        for i in range(20):
            session_service.add_message(sid, MessageRole.USER, f"msg-{i}")
        ctx = session_service.get_conversation_context(sid, max_messages=5)
        lines = ctx.strip().split("\n")
        assert len(lines) == 5
        # Should be the last 5 messages
        assert "msg-15" in lines[0]
        assert "msg-19" in lines[4]

    def test_empty_session(self, session_service):
        sid = session_service.create_session()
        assert session_service.get_conversation_context(sid) == ""

    def test_missing_session(self, session_service):
        assert session_service.get_conversation_context("nope") == ""


# ---------- list_sessions ----------


class TestListSessions:
    def test_empty(self, session_service):
        assert session_service.list_sessions() == []

    def test_multiple(self, session_service):
        session_service.create_session(name="A")
        session_service.create_session(name="B")
        infos = session_service.list_sessions()
        assert len(infos) == 2
        names = {i.name for i in infos}
        assert names == {"A", "B"}


# ---------- Session expiration ----------


class TestSessionExpiration:
    def test_expired_sessions_cleaned_on_create(self, session_service):
        sid = session_service.create_session(name="old")
        # Manually backdate the session
        past = datetime.utcnow() - SESSION_TTL - timedelta(seconds=1)
        session_service._sessions[sid]["updated_at"] = past

        # Creating a new session triggers cleanup
        session_service.create_session(name="new")
        assert session_service.get_session(sid) is None
        assert len(session_service.list_sessions()) == 1
