"""Tests for Pydantic models in api.models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from api.models import (
    ChatRequest,
    ChatMessage,
    ColumnInfo,
    QueryResult,
    EnrichmentMetadata,
    CalculationMetadata,
    CalculatedColumnInfo,
    SessionInfo,
    Insight,
    ClarifyingQuestion,
    MessageRole,
)


# ---------- ChatRequest ----------


class TestChatRequest:
    def test_valid_request(self):
        req = ChatRequest(message="Show me sales by state")
        assert req.message == "Show me sales by state"
        assert req.session_id is None

    def test_with_session_id(self):
        req = ChatRequest(message="hello", session_id="abc-123")
        assert req.session_id == "abc-123"

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_max_length_enforced(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 10001)

    def test_max_length_boundary(self):
        req = ChatRequest(message="x" * 10000)
        assert len(req.message) == 10000


# ---------- ChatMessage ----------


class TestChatMessage:
    def test_defaults(self):
        msg = ChatMessage(id="1", role=MessageRole.USER, content="hi")
        assert msg.is_streaming is False
        assert msg.insights == []
        assert msg.query_result is None
        assert msg.clarifying_question is None

    def test_timestamp_auto(self):
        msg = ChatMessage(id="1", role=MessageRole.ASSISTANT, content="hello")
        assert isinstance(msg.timestamp, datetime)


# ---------- ColumnInfo ----------


class TestColumnInfo:
    def test_defaults(self):
        col = ColumnInfo(name="state", type="STRING")
        assert col.is_enriched is False
        assert col.is_calculated is False

    def test_enriched(self):
        col = ColumnInfo(name="_enriched_capital", type="STRING", is_enriched=True)
        assert col.is_enriched is True
        assert col.is_calculated is False

    def test_calculated(self):
        col = ColumnInfo(name="ratio", type="FLOAT64", is_calculated=True)
        assert col.is_calculated is True
        assert col.is_enriched is False


# ---------- QueryResult ----------


class TestQueryResult:
    def test_minimal(self):
        qr = QueryResult(
            columns=[ColumnInfo(name="a", type="STRING")],
            rows=[{"a": "x"}],
            total_rows=1,
            query_time_ms=10.0,
            sql="SELECT a FROM t",
        )
        assert qr.enrichment_metadata is None
        assert qr.calculation_metadata is None

    def test_with_enrichment_metadata(self):
        qr = QueryResult(
            columns=[ColumnInfo(name="a", type="STRING")],
            rows=[],
            total_rows=0,
            query_time_ms=0,
            sql="SELECT 1",
            enrichment_metadata=EnrichmentMetadata(
                source_column="a",
                enriched_fields=["capital"],
                total_enriched=5,
            ),
        )
        assert qr.enrichment_metadata.source_column == "a"
        assert qr.enrichment_metadata.partial_failure is False

    def test_with_calculation_metadata(self):
        qr = QueryResult(
            columns=[ColumnInfo(name="a", type="FLOAT64")],
            rows=[],
            total_rows=0,
            query_time_ms=0,
            sql="SELECT 1",
            calculation_metadata=CalculationMetadata(
                calculated_columns=[
                    CalculatedColumnInfo(name="ratio", expression="a / b")
                ],
                warnings=["Row 3: Division by zero"],
            ),
        )
        assert len(qr.calculation_metadata.calculated_columns) == 1
        assert qr.calculation_metadata.warnings[0].startswith("Row 3")


# ---------- SessionInfo ----------


class TestSessionInfo:
    def test_construction(self):
        now = datetime.utcnow()
        info = SessionInfo(
            id="sid-1",
            name="My Session",
            created_at=now,
            updated_at=now,
            message_count=5,
        )
        assert info.id == "sid-1"
        assert info.message_count == 5


# ---------- Insight ----------


class TestInsight:
    def test_defaults(self):
        ins = Insight(type="trend", message="Sales are up")
        assert ins.importance == "medium"

    def test_custom_importance(self):
        ins = Insight(type="anomaly", message="Outlier", importance="high")
        assert ins.importance == "high"


# ---------- ClarifyingQuestion ----------


class TestClarifyingQuestion:
    def test_defaults(self):
        cq = ClarifyingQuestion(question="Which region?")
        assert cq.options == []
        assert cq.context is None

    def test_with_options(self):
        cq = ClarifyingQuestion(
            question="Which metric?",
            options=["revenue", "profit"],
            context="Choosing KPI",
        )
        assert len(cq.options) == 2
        assert cq.context == "Choosing KPI"
