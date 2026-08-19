# Chronicle — Implementation Status

Last updated: 2026-08-19

This document is a live implementation snapshot intended for context handoff to other AI-assisted sessions. It complements `/home/runner/work/chronicle/chronicle/README.md` with concrete current-state details.

## 1) Current Scope (Implemented vs Planned)

### Implemented and active
- Orchestrator agent: **Library Director** (`src/chronicle/agents/library_director.py`)
- Specialist agent: **Librarian Decision Logger** (`src/chronicle/agents/librarian_decision_logger.py`)
- Specialist agent: **Librarian Glossary Curator** (`src/chronicle/agents/librarian_glossary_curator.py`)
- Evaluation agent: **Auditor** (`src/chronicle/audit/auditor.py`)
- Pipeline orchestrator: **ChroniclePipeline** (`src/chronicle/pipeline/chronicle_pipeline.py`)
- CLI entrypoint: `python -m chronicle` (`src/chronicle/__main__.py`)

### Planned / not yet implemented as active specialists
- Librarian Risk Curator
- Librarian Status Keeper
- Librarian Change Historian
- Librarian Question Tracker

The pipeline already supports adding new specialists via `ChroniclePipeline.register_specialist(...)`.

## 2) Runtime Flow (As Implemented Today)

For each `.md` file in the configured raw directory (alphabetical order):
1. Library Director produces a JSON execution plan.
2. Plan is written to `out/plan.json` during execution.
3. Specialists run only for affected files with registered handlers.
4. Decision entries are generated, then reversed, then inserted at top of `compiled/decision-log.md`.
5. Glossary entries are generated and appended to `compiled/glossary.md`.
6. Auditor runs periodically (`--audit-every`) and/or end-of-run (`--audit-now` / default end behavior).
7. Intermediate artifacts in `out/` are cleaned up automatically at end of directory processing.

## 3) Data/Artifacts Snapshot in Repository

### Inputs
- Raw artifacts currently present under: `/home/runner/work/chronicle/chronicle/raw/meetings/2026/`

### Compiled knowledge base (current content counts)
- `compiled/decision-log.md`: **37** `DEC-...` entries
- `compiled/glossary.md`: **5** term headings

### Audit outputs
- Existing reports in `/home/runner/work/chronicle/chronicle/reports/`:
  - `audit-report-2026-07-21-001.md`
  - `audit-report-2026-07-21-002.md`
  - `audit-report-2026-07-21-003.md`

## 4) Audit Capability (Current)

### Deterministic checks (implemented)
1. `duplicate-dec-id`
2. `malformed-dec-id`
3. `decision-missing-references`
4. `glossary-missing-introduced-in`
5. `duplicate-glossary-heading`

### Semantic checks (implemented)
- `glossary-semantic-duplicates` (LLM)
- `decision-semantic-duplicates` (LLM)

Auditor behavior:
- Makes at most 2 LLM calls per audit run (one glossary, one decision check; each can be skipped by preconditions).
- Produces findings consumed by report renderer in `src/chronicle/audit/report.py`.

## 5) Interfaces and Contracts to Preserve

- Library Director output must remain strict JSON:
  - `{"affected_files": [{"path", "operation", "why", "raw_refs"}]}`
- Decision Logger output must contain:
  - `append_to`, `new_entries_markdown`
- Glossary Curator output must contain:
  - `append_to`, `new_entries_markdown`
- JSON parsing/validation guardrail:
  - `safe_parse_json(...)` in `src/chronicle/io/json_utils.py`

These contracts are relied on directly by pipeline dispatch and payload handling.

## 6) Configuration and Execution

### Required environment variables
- `ENDPOINT_URL`
- `DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_KEY`

Loaded by `AzureOpenAIClient.from_env()` (`src/chronicle/llm/azure_openai_client.py`).

### Main CLI defaults
- `--raw-dir`: `raw/meetings/2026`
- `--compiled-dir`: `compiled`
- `--agents-dir`: `agents`
- `--schema-dir`: `schema`
- `--out-dir`: `out`
- `--reports-dir`: `reports`
- `--audit-every`: `5`
- `--audit-now`: off by default
- `--no-audit`: off by default

## 7) Testing Status

- Test framework: `pytest`
- Test files under `/home/runner/work/chronicle/chronicle/tests/`
- Current unit test count in repository: **147** test functions

## 8) Known Gaps / Next-Step Opportunities

1. Implement additional specialist agents beyond decision/glossary.
2. Add richer cross-file consistency enforcement using `/schema/cross-file-consistency.md`.
3. Add human review / approval workflow for audit findings.
4. Improve storage options beyond markdown-only compiled outputs.
5. Add operational telemetry aggregation from token logs and audit reports.

## 9) Maintenance Rule for This Document

When functionality changes, update this file in the same PR/session, especially:
- active agents and responsibilities
- CLI/runtime behavior
- audit checks and report behavior
- contract/interface expectations
- snapshot counts/date-sensitive status values

