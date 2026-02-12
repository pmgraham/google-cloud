"""Structured observability for agent runs.

Provides OTEL-compatible JSON logging for Google Cloud Logging with three
concerns:

1. **Run summaries** — Each agent invocation emits one structured log with
   duration, event count, outcome, and which agents participated.  This is
   the primary signal for dashboards and alerting.

2. **Decision traces** — The ordered sequence of tool calls (with the agent
   that made each call) is captured in ``tool_sequence``.  For failed or
   timed-out runs this reveals *what the agent was doing* when it got stuck,
   which is essential for debugging non-deterministic LLM behavior.

3. **Outcome classification** — Every run is labelled as one of ``success``,
   ``timeout``, ``error``, ``empty``, or ``safety_filtered``.  The last
   category uses two tiers of detection: exact refusal phrases for
   model-level safety filters (Tier 1), and a structural check that
   combines agent behaviour (no data-returning tool was called) with
   broad privacy keywords (Tier 2).  The structural tier is resilient to
   LLM rephrasing because it relies on what the agent *did*, not the
   exact words it chose.

Log format follows the Google Cloud Logging structured JSON convention so
that entries written to stdout on Cloud Run / GKE are automatically parsed
into queryable fields under ``jsonPayload``.

Example Cloud Logging queries::

    jsonPayload.severity="WARNING"
    jsonPayload.agent_run.outcome="timeout"
    jsonPayload.agent_run.duration_ms > 10000
    labels.outcome="safety_filtered"

.. warning:: Privacy — NOT production-ready as-is

   This module is part of a training / illustration codebase and
   intentionally logs fields that contain user content (``prompt_preview``,
   ``response_preview``, ``session_id``).  **A production deployment must
   add the following controls before serving real users:**

   1. **PII redaction** — Run ``prompt_preview``, ``response_preview``, and
      any SQL snippets through Google Cloud DLP API (or equivalent) to
      detect and mask emails, names, phone numbers, credit card numbers,
      and other personally identifiable information before they reach the
      log sink.

   2. **Prompt logging opt-in** — Do not log user prompt content by default.
      Gate ``prompt_preview`` behind an explicit user consent toggle (e.g.
      "Help improve this product by sharing your conversations").  Without
      consent, log only operational fields (outcome, duration, tool_sequence,
      event_count).

   3. **Separate log sinks with access controls** — Route logs containing
      user content to a restricted Cloud Logging bucket with tight IAM
      policies and audit logging, separate from the operational log bucket
      that on-call engineers access day-to-day.

   4. **Retention limits** — Set Cloud Logging retention policies (e.g.
      30–90 days for operational logs, shorter for content-bearing logs).
      Longer retention increases liability surface with minimal diagnostic
      benefit.

   5. **Session ID pseudonymisation** — ``session_id`` is linkable to a
      user's full conversation history.  In production, consider hashing or
      tokenising it in logs so that correlating sessions requires access to
      a separate mapping table with its own access controls.

   6. **Aggregate over inspect** — For product-improvement analytics, prefer
      aggregate queries ("what % of enrichment requests time out?") over
      inspecting individual prompts.  Design dashboards around operational
      fields so that accessing user content is the exception, not the norm.

.. note:: Adversarial hardening & continuous improvement

   The two-tier outcome classification (exact refusal phrases + structural
   behaviour) is sufficient for basic dashboarding, but a production agent
   exposed to untrusted users should extend the observability layer in
   several directions.

   **Hardening the agent against adversarial prompts:**

   1. **Input pre-screening** — Before the prompt reaches the ADK runner,
      run it through a lightweight classifier (e.g. Vertex AI text
      classification or an embedding-similarity check against known attack
      templates) to flag jailbreak attempts, prompt injections, and
      off-topic abuse.  This is cheaper than a full LLM call and can
      short-circuit the request before any tools fire.

   2. **Query cost gating** — Use the BigQuery dry-run ``total_bytes_processed``
      estimate (already available from ``validate_sql_query``) to reject
      queries that exceed a per-request byte budget.  This prevents
      resource-exhaustion attacks like unbounded cross-joins.

   3. **Output validation** — After the agent responds, check that the
      response does not leak system prompts, internal tool names, or
      schema details that were not part of the user's query.  A simple
      keyword scan for instruction-preamble fragments is a low-cost
      first pass.

   4. **Rate limiting** — Enforce per-session and per-user request rate
      limits at the API layer.  Repeated requests to the same session
      in a short window are a signal of automated probing.

   **Using observability data to improve the agent over time:**

   5. **Refusal subcategories** — Split ``safety_filtered`` into finer
      labels (``privacy_refusal``, ``off_topic``, ``capability_limit``,
      ``jailbreak_attempt``) so dashboards can track each category
      independently.  The Tier 2 structural pattern generalises:
      each new subcategory is a (tool-usage signal + keyword set) pair.

   6. **Cross-session anomaly detection** — Track refusal rates per
      session and per user over time.  A single privacy refusal is
      normal; ten in a row from the same session suggests probing.
      Cloud Monitoring alerting policies on ``labels.outcome`` can
      surface these patterns.

   7. **Human review queue** — Route runs with ambiguous classification
      (e.g. agent called no tools and used no known refusal language)
      to a review queue for manual labelling.  Labelled examples feed
      back into the keyword lists and structural signals, creating a
      continuous improvement loop.

   8. **Feedback-driven prompt engineering** — Aggregate outcome data
      (which tool sequences lead to timeouts?  which prompt patterns
      trigger safety filters?) to identify weaknesses in the system
      instruction.  For example, a high ``timeout`` rate on enrichment
      requests might indicate the enrichment agent's instructions need
      tighter scoping, not a code change.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------

# Python log level → Google Cloud Logging / OTEL severity text
_SEVERITY_MAP: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


class _StructuredFormatter(logging.Formatter):
    """Emit each log record as a single JSON line.

    Special fields recognised by Cloud Logging
    (``severity``, ``timestamp``, ``logging.googleapis.com/labels``)
    are placed at the top level.  Everything else lands in
    ``jsonPayload`` automatically.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "severity": _SEVERITY_MAP.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Merge caller-supplied structured attributes
        attrs = getattr(record, "attributes", None)
        if isinstance(attrs, dict):
            entry.update(attrs)

        # Promote high-cardinality filter keys into Cloud Logging labels
        # so they become indexed and cheap to query.
        labels = getattr(record, "labels", None)
        if isinstance(labels, dict):
            entry["logging.googleapis.com/labels"] = labels

        return json.dumps(entry, default=str)


def get_logger(name: str = "agent.observability") -> logging.Logger:
    """Return a JSON-structured logger, creating it on first call."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

# -- Tier 1: High-confidence exact-phrase patterns -------------------------
# These fire regardless of tool usage.  They catch unambiguous model-level
# safety refusals ("I can't help with that", "content policy", etc.).
_SAFETY_REFUSAL_PATTERNS = re.compile(
    "|".join(
        [
            # can(?:'?t|not) matches "can't", "cant", and "cannot".
            r"i can(?:'?t|not) help with that",
            r"i(?:'m| am) not able to assist",
            r"i cannot assist",
            r"i(?:'m| am) unable to help",
            r"against my .* guidelines",
            r"content policy",
            r"i(?:'m| am) not able to provide",
            r"potentially harmful",
            r"i can(?:'?t|not) generate",
            r"i(?:'m| am) not able to generate",
            r"violates .* policy",
            r"blocked by safety",
        ]
    ),
    re.IGNORECASE,
)

# -- Tier 2: Structural (behavioural) refusal detection --------------------
# Instead of trying to anticipate every refusal phrasing, Tier 2 looks at
# what the agent *did*.  If the agent never called a data-returning tool
# (i.e. it inspected schemas but chose not to query), AND the response
# contains privacy-adjacent language, the run is classified as
# safety_filtered.
#
# Because the keyword list is gated by the structural signal, it can be
# much broader than Tier 1 without producing false positives — a response
# that mentions "privacy" after successfully returning query results will
# NOT be misclassified.

# Tools whose invocation means the agent actively tried to fulfil the
# user's data request.  Their presence in the tool sequence is a strong
# counter-signal against a refusal classification.
_DATA_TOOLS = frozenset(
    {
        "execute_query_with_metadata",
        "apply_enrichment",
        "add_calculated_column",
    }
)

# Broad privacy / refusal keywords — only consulted when no data tool ran.
_PRIVACY_REFUSAL_SIGNALS = re.compile(
    "|".join(
        [
            r"personally identifiable",
            r"\bpii\b",
            r"sensitive (?:data|information)",
            r"confidential",
            r"data (?:protection|safety|privacy)",
            r"user privacy",
            r"protect(?:ing)? (?:user|customer|personal)",
            r"not (?:appropriate|advisable) to (?:share|display|dump|expose)",
            r"i cannot provide",
            r"i can'?t provide",
        ]
    ),
    re.IGNORECASE,
)


def classify_outcome(
    response_text: str,
    event_count: int,
    *,
    timed_out: bool = False,
    error: Exception | None = None,
    tool_sequence: list[dict[str, str]] | None = None,
) -> str:
    """Classify the result of a single agent run.

    Uses two tiers of detection for safety-filtered outcomes:

    * **Tier 1 (exact patterns):** High-confidence model-level refusal
      phrases that indicate a safety filter regardless of tool usage.
    * **Tier 2 (structural + keywords):** If the agent never called a
      data-returning tool *and* the response contains privacy-adjacent
      language, the run is classified as a refusal.  This is resilient
      to rephrasing because it relies on agent *behaviour* (what tools
      it called) rather than exact wording.

    Returns one of:
        ``success``          – agent produced a meaningful response.
        ``timeout``          – agent exceeded the deadline.
        ``error``            – an unhandled exception was raised.
        ``empty``            – run completed but produced no text.
        ``safety_filtered``  – refusal detected via exact patterns (Tier 1)
                               or behavioural + keyword signals (Tier 2).
    """
    if timed_out:
        return "timeout"
    if error is not None:
        return "error"
    if not response_text or not response_text.strip():
        return "empty"

    # Tier 1: unambiguous refusal phrases
    if _SAFETY_REFUSAL_PATTERNS.search(response_text):
        return "safety_filtered"

    # Tier 2: agent chose not to query data + privacy language present
    if tool_sequence is not None:
        tools_used = {step["tool"] for step in tool_sequence}
        ran_data_tool = bool(tools_used & _DATA_TOOLS)
        if not ran_data_tool and _PRIVACY_REFUSAL_SIGNALS.search(response_text):
            return "safety_filtered"

    # Production extension point: additional structural tiers go here.
    # Each new tier follows the same pattern as Tier 2:
    #   (behavioural signal from tool_sequence) + (keyword set) → outcome
    #
    # Examples:
    #   - Off-topic:  no tools called at all + redirect language
    #     ("I'm designed for data analysis", "try asking about")
    #   - Jailbreak:  no tools called + injection language
    #     ("ignore previous", "act as", "you are now")
    #   - Probing:    repeated schema-only tool calls across the session
    #     (requires cross-request state, not available here)
    #
    # See the module docstring's "Adversarial hardening" note for the
    # full production roadmap.

    return "success"


# ---------------------------------------------------------------------------
# Agent Run Tracer
# ---------------------------------------------------------------------------


class AgentRunTracer:
    """Accumulate per-run metrics and emit a structured log on completion.

    Instantiate at the start of a ``/api/chat`` request, call
    :meth:`record_event` inside the event loop, then :meth:`complete`
    once the run finishes (or times out / errors).

    The final structured log contains everything needed to diagnose
    both traditional service failures and non-deterministic LLM issues:

    * **Run summary** — duration, event count, outcome, participating agents.
    * **Decision trace** — ordered ``tool_sequence`` showing each tool call
      and which agent made it, so you can reconstruct the agent's reasoning
      path when a run fails or times out.
    * **Outcome label** — one of ``success`` / ``timeout`` / ``error`` /
      ``empty`` / ``safety_filtered``, used for filtering and alerting in
      Cloud Logging dashboards.
    """

    def __init__(self, session_id: str, prompt: str) -> None:
        self._logger = get_logger()
        self.session_id = session_id
        self.prompt_preview = prompt[:200]
        self.start_time = time.monotonic()
        self.tool_sequence: list[dict[str, str]] = []
        self.agents_involved: set[str] = set()
        self.event_count = 0

    # -- recording helpers --------------------------------------------------

    def record_event(
        self,
        author: str,
        tool_calls: list[str] | None = None,
    ) -> None:
        """Record one ADK event.

        Args:
            author: The agent name that authored this event.
            tool_calls: Tool names invoked in this event (if any).
        """
        self.event_count += 1
        if author and author != "?":
            self.agents_involved.add(author)
        for name in tool_calls or []:
            self.tool_sequence.append({"agent": author, "tool": name})

    # -- completion ---------------------------------------------------------

    def complete(
        self,
        response_text: str = "",
        *,
        timed_out: bool = False,
        error: Exception | None = None,
    ) -> str:
        """Classify the outcome, emit the structured log, return the outcome.

        Returns:
            The outcome string (``success``, ``timeout``, etc.) so the
            caller can branch on it without re-classifying.
        """
        duration_ms = round((time.monotonic() - self.start_time) * 1000)

        outcome = classify_outcome(
            response_text,
            self.event_count,
            timed_out=timed_out,
            error=error,
            tool_sequence=self.tool_sequence,
        )

        severity = logging.INFO if outcome == "success" else logging.WARNING

        # -- build the structured payload ----------------------------------
        agent_run: dict[str, Any] = {
            "session_id": self.session_id,
            "prompt_preview": self.prompt_preview,
            "duration_ms": duration_ms,
            "event_count": self.event_count,
            "outcome": outcome,
            "tool_sequence": self.tool_sequence,
            "agents_involved": sorted(self.agents_involved),
        }

        if error is not None:
            agent_run["error_type"] = type(error).__name__
            agent_run["error_detail"] = str(error)[:500]

        if outcome == "safety_filtered":
            agent_run["response_preview"] = response_text[:300]

        if outcome == "timeout":
            agent_run["timeout_seconds"] = duration_ms / 1000

        # Cloud Logging indexed labels for fast filtering
        labels = {
            "outcome": outcome,
            "session_id": self.session_id,
        }

        self._logger.log(
            severity,
            f"agent run {outcome} ({duration_ms}ms, {self.event_count} events)",
            extra={
                "attributes": {"agent_run": agent_run},
                "labels": labels,
            },
        )

        return outcome
