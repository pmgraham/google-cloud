# Industrial Parts Matching Pipeline & Agent

## Overview
The Industrial Parts Matching project aims to solve the complex challenge of aligning a customer's proprietary or generic parts catalog with supplier catalog items. Exact-match logic fails for the vast majority of parts due to differences in abbreviations, missing dimensions, implicit standards, and differing part number formats.

This project implements a **Hybrid AI Matching Architecture** to solve this problem, leveraging the strengths of BigQuery's native AI processing for scale, and the reasoning capabilities of an autonomous Go-based reasoning agent for precision.

## Quick Start

The entire BigQuery infrastructure (schemas, tables, ML models, vector indexes, and configuration) is managed by a single Python orchestrator script. The orchestrator also handles the compilation and execution of the Go agent.

```bash
# Install dependencies
uv sync

# Provision the BigQuery Infrastructure, run the Bulk Matching ML, and execute the Go Agent
uv run python pipeline/run.py
```

---

## The Hybrid Approach

The logic is split into two complementary phases to maximize both scale and accuracy without over-engineering either segment:

### Phase 1: The Bulk Vector Search Pipeline (BigQuery)

When the initial data is loaded into BigQuery, plain SQL rules are not enough to bridge the gap between "SCREW M16" and "M16X1.5 Hex Bolt".

1.  **AI Data Extraction (`pipeline/sql/templates/02_ai_generation.sql.jinja`)**: 
    We use BigQuery's `AI.GENERATE_TEXT` with a Gemini model to read the messy, raw `part_description` fields and structure them into a standardized JSON format (extracting `part_type`, `size_value`, `material`, etc.).
2.  **Semantic Embeddings (`pipeline/sql/templates/02b_embeddings.sql.jinja`)**: 
    We use `AI.GENERATE_EMBEDDING` to create mathematical vector representations of the internal text. This captures the *meaning* of the part, resolving abbreviations and synonyms.
3.  **Vector Search & Lexical Scoring (`pipeline/sql/templates/03_match_groups.sql.jinja`)**: 
    We perform a `VECTOR_SEARCH` to find the closest semantic neighbors for every customer part against the supplier database. **Crucially, this search is performed globally across all normalized supplier catalogs (`source != 'Customer'`). Every customer part is mathematically evaluated against every possible supplier simultaneously.** We combine this Vector Distance with a Lexical Edit Distance (comparing the text characters) and calculate a Reciprocal Rank Fusion (RRF) score.
    *High-confidence matches are pushed directly to `auto_approved_matches`, while borderline edge cases are queued for human or agent review in `agent_review_queue`.*

**Bulk Pipeline Results**: This highly configurable Jinja-SQL pipeline processes the entire catalog and successfully resolves ~90% of the true matching pairs natively.

### Phase 2: The Tenacious Validation Agent (Go)

The bulk pipeline deliberately leaves roughly 10% of the parts unmatched. These are the exceptions: parts with missing critical dimensions, highly generic descriptions (e.g., "HOSE"), or proprietary internal IDs that require research to decode. 

Rather than building infinitely complex SQL logic to handle edge cases, we deploy a persistent, autonomous AI Agent written in Go (`go-agent/main.go`) and powered by the **Vertex AI Go SDK**. 

The Agent executes the following loop:
1.  **Read Exceptions**: It queries BigQuery for the remaining customer parts explicitly paired with their borderline supplier candidates from the `agent_review_queue`.
2.  **Concurrent Execution**: It uses a high-concurrency worker pool with a Multi-Pass Dead Letter Queue (DLQ) strategy to ensure every part is evaluated even if the LLM occasionally returns malformed responses.
3.  **Logical Verification**: The Agent evaluates the evidence just like an engineer. It understands that a supplier's "Black Oxide" finish is an acceptable addition to a customer's generic requirement, but it will correctly refuse to match a "M10 Bolt" to a "M16 Bolt". 
4.  **Final Decision**: It explicitly records its decision (MATCH, NO_MATCH, REQUIRES_HUMAN_REVIEW) back into the `agent_decisions` BigQuery table. 
5.  **SLA Tracking**: Both pipeline stages secure a `created_at` timestamp on their respective tables. Subtracting `agent_decisions.created_at` from `agent_review_queue.created_at` provides exact operational SLA tracking on AI matching velocity. These decisions are seamlessly aggregated into the final product via the `05_final_mapping` view.

**Agent Results**: The agent acts as the system's reasoning safety net. It correctly rejects borderline candidates flagged by the vector pipeline, proving matches for obscure items, and rightfully tagging completely generic items as `REQUIRES_HUMAN_REVIEW` to prevent bad matches from corrupting the ecosystem model.

---

## Expected Outcomes & Pipeline Results

When a user runs the full pipeline orchestrator (`uv run python pipeline/run.py`), they will see the data transform from raw configuration into a fully evaluated mapping graph.

### 1. High-Confidence Matches
The bulk of the matches are resolved natively inside BigQuery within minutes using vector search and strict thresholding. This produces a massive, scalable baseline of paired parts. 

### 2. Deep Qualitative Reasoning
For the exceptions picked up by the Go Agent, users can query the `agent_decisions` table to see the exact logic used to resolve the conflict. For example:

*   **MATCH Resolution Example**: 
    > *"Customer part 'ORING 15MM IDX2.0MM CS' perfectly matches supplier part 'FAS-O-RING-00011' (O-RING 15MM ID X 2.0MM CS VITON) in type, inner diameter, and cross-section."*
*   **REQUIRES_HUMAN_REVIEW Safeties**: 
    > *"The customer part 'ERP-1000031' has only a generic description 'HOSE'. Web search provided no public specifications. The candidate 'FAS-HOSE-00041' is described as 'HOSE FKM'. Without knowing the material (e.g., FKM) or other critical dimensions ... a definitive match cannot be made."*

### Conclusion
By blending the brute-force scalability of BigQuery AI with the flexible, investigative logic of an autonomous Go reasoning agent, we have created a parts-matching system that achieves near-perfect evaluation coverage (analyzing 100% of exceptions) while guaranteeing high precision and safety against hallucinations.
