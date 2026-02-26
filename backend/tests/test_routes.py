"""Tests for API route helpers in api.routes."""

from api.routes import parse_agent_response


class TestParseAgentResponse:
    def test_no_question(self):
        result = parse_agent_response("Here are your sales results.")
        assert result["clarifying_question"] is None
        assert result["summary"] == "Here are your sales results."

    def test_question_with_options(self):
        text = (
            "I found multiple tables. Which table would you like to query?\n"
            "- sales_data\n"
            "- customer_info\n"
            "- inventory"
        )
        result = parse_agent_response(text)
        cq = result["clarifying_question"]
        assert cq is not None
        assert "Which table" in cq.question
        assert len(cq.options) == 3
        assert "sales_data" in cq.options

    def test_question_without_options(self):
        text = "Here is the data. Do you want more detail?"
        result = parse_agent_response(text)
        # Question is present but no bullet options → no clarifying_question extracted
        assert result["clarifying_question"] is None

    def test_numbered_options(self):
        text = (
            "There are several metrics. What metric do you want?\n"
            "1. Revenue\n"
            "2. Profit\n"
            "3. Margin"
        )
        result = parse_agent_response(text)
        cq = result["clarifying_question"]
        assert cq is not None
        assert len(cq.options) == 3

    def test_max_five_options(self):
        text = (
            "Which one? What would you like?\n"
            "- a\n- b\n- c\n- d\n- e\n- f\n- g"
        )
        result = parse_agent_response(text)
        cq = result["clarifying_question"]
        assert cq is not None
        assert len(cq.options) <= 5
