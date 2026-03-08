# DataGrunt Agent — Roadmap

## Future Planning Tasks

### Phase 3: Agent Engine Deployment (GCS I/O)

**Status**: Planning
**Priority**: High
**Dependencies**: None (parallel to current work)

Refactor file I/O to support Google Cloud Agent Engine's stateless environment.

**Context**:
- Agent Engine doesn't support persistent local filesystem
- Current implementation assumes local file paths
- User uploads arrive via Gemini Enterprise
- Outputs must be persisted to GCS

**Required Changes**:
- Replace local file paths with GCS URIs throughout the codebase
- Configure DuckDB's httpfs extension to read/write directly to GCS
- Abstract file I/O behind a configurable interface to support:
  - Local file paths (development/testing)
  - GCS URIs (production in Agent Engine)
- Update configuration to switch between environments

**Acceptance Criteria**:
- All file operations use abstract I/O interface
- DuckDB can read/write CSV, Parquet, Excel files from GCS
- Local development still works with filesystem paths
- Production deployment uses GCS URIs without code changes

---

### Phase 4: Large File Handling (100M+ rows)

**Status**: Planning
**Priority**: High
**Dependencies**: Phase 3 (GCS I/O foundation)

Implement strategy for processing very large files (100M+ rows) in stateless Agent Engine environment.

**Context**:
- Current DuckDB in-memory approach doesn't scale to massive files
- Agent Engine has limited memory and no persistent local disk
- Need to handle extremely large files without memory exhaustion

**Key constraint**: The whole point of this agent is to clean/repair data that is too malformed for BigQuery or Parquet conversion. The agent must do the cleaning first — routing raw dirty data to BigQuery defeats the purpose.

**Recommended approach — Chunked/Streaming Processing**:
- Read CSV from GCS in fixed-size chunks (e.g. 1M rows)
- Run the full repair pipeline on each chunk (header detection on first chunk, delimiter/quoting/type coercion on all)
- Write clean Parquet chunks to GCS as they complete
- Concat or load to BQ from clean Parquet after all chunks processed
- Pros: Works with any format, no local disk needed, full repair pipeline applies
- Cons: Cross-chunk patterns harder to detect (e.g. schema drift between chunks), header detection only from first chunk

**Decision Process**:
- Profile memory constraints in Agent Engine
- Test with 100M+ row sample files
- Determine max chunk size that fits in Agent Engine memory
- Validate that chunk-level repair produces same results as full-file repair

**Acceptance Criteria**:
- System can process files with 100M+ rows without OOM errors
- Clear error handling and user messaging for files exceeding limits
- Performance benchmarks documented for each file size tier
- Strategy clearly documented for maintainability

