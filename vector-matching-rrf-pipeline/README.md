# Industrial Parts Matching Pipeline

This repository contains an end-to-end data processing and reasoning pipeline built on Google Cloud to harmonize disparate industrial parts catalogs. 

It uses a dual-architecture approach:
1. **BigQuery Bulk Matching Pipeline:** Resolves 90% of parts automatically using Vector Distance indexing and Gemini-driven attribute extraction via BigQuery ML natively in SQL.
2. **Go Reasoning Agent:** Spins up an autonomous reasoning agent powered by Vertex AI that investigates the remaining 10% edge-cases to verify complex engineering specifications before making a final decision.

### Deployment 

The entire BigQuery infrastructure (schemas, tables, ML models, vector indexes, and configuration) is managed by a single Python orchestrator script. The orchestrator also handles the compilation and execution of the Go agent.

```bash
# Provision the BigQuery Infrastructure, run the Bulk Matching ML, and execute the Go Agent
uv run python pipeline/run.py
```

For a detailed technical walkthrough of the architecture, please see `docs/README.md`.
