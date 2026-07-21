# Chronicle

**Chronicle — A Multi-Agent LLM System for Continuous Project Knowledge Compilation**

> *Can a coordinated system of specialized LLM agents continuously transform raw project artifacts into structured, traceable organizational knowledge — maintaining consistency and quality through orchestration, structural guardrails, and shared external memory?*

Chronicle is a small multi-agent architecture built for an Intelligent Agents course final project. It is not a chatbot or a single script: it is a pipeline of cooperating LLM-based agents, each with a defined role, operating over a shared external knowledge base with structural guardrails enforced at every step.

---

## Intelligent Agents Architecture

Chronicle maps directly onto the core concepts of the Intelligent Agents course:

| Repository Layer | Intelligent Agents Concept            |
|------------------|---------------------------------------|
| `raw/`           | Artifact / input layer                |
| `compiled/`      | Shared external memory / knowledge base |
| `schema/`        | Structural guardrails                 |
| `agents/`        | Agent definitions / system prompts    |
| `tools/`         | Agent harness and execution scripts   |
| `reports/`       | Evaluation outputs                    |
| `out/`           | Intermediate artifacts                |

### Agent Hierarchy

**Compilation Pipeline** (processes each raw artifact):

```
Library Director  (Orchestrator Agent)
│
├── Librarian Decision Logger      [Active]
├── Librarian Glossary Curator     [Active]
├── Librarian Risk Curator         [Future]
├── Librarian Status Keeper        [Future]
├── Librarian Change Historian     [Future]
└── Librarian Question Tracker     [Future]
```

**Evaluation Layer** (after compilation):

```
Auditor  (Evaluation Agent)
├── Deterministic Checks (5 structural validations)
└── Semantic Checks (via LLM: glossary + decision near-duplicates)
```

- **Library Director** — Analyzes a raw artifact and produces a JSON execution plan. Decides which specialist librarian agents to invoke. Does not write to `compiled/` directly.
- **Librarian Decision Logger** — Extracts decisions from the raw artifact and writes structured entries to `compiled/decision-log.md`, following the schema in `schema/compiled-templates/`.
- **Librarian Glossary Curator** — Extracts glossary terms from the raw artifact and writes structured entries to `compiled/glossary.md`, with traceability metadata.
- **Auditor** — Evaluates the compiled knowledge base for structural and semantic issues. Runs after each batch of compilation and produces an audit report.

Chronicle is designed to be **storage-compatible**: compiled knowledge is stored as plain Markdown files in the local filesystem and is compatible with version control, but the system does not depend on any specific storage backend.

---

## Repository Structure

```
chronicle/
├── agents/                        # Agent definitions / system prompts
│   ├── library-director.md
│   ├── librarian-decision-logger.md
│   ├── librarian-glossary-curator.md
│   └── auditor.md
│
├── compiled/                      # Shared external memory / knowledge base
│   ├── decision-log.md
│   └── glossary.md
│
├── raw/                           # Artifact / input layer (read-only)
│   └── meetings/
│
├── schema/                        # Structural guardrails
│   ├── cross-file-consistency.md
│   └── compiled-templates/
│       ├── decision-log.md
│       ├── glossary.md
│       └── ...
│
├── src/chronicle/                 # Agent harness (Python package)
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── library_director.py
│   │   ├── librarian_decision_logger.py
│   │   └── librarian_glossary_curator.py
│   ├── audit/
│   │   ├── auditor.py
│   │   ├── checks.py              # Deterministic structural checks
│   │   └── report.py              # Report generation
│   ├── llm/
│   │   ├── azure_openai_client.py
│   │   └── token_logger.py
│   ├── io/
│   │   ├── prompt_loader.py
│   │   ├── json_utils.py
│   │   └── knowledge_base.py
│   ├── pipeline/
│   │   └── chronicle_pipeline.py
│   └── __main__.py
│
├── tools/
│   ├── run_chronicle.ps1          # Console entrypoint
│   ├── run_model_test_AzureOpenAI.py
│   └── tokens_usage.py
│
├── tests/                         # Unit test suite (147 tests)
├── out/                           # Intermediate artifacts (plan.json, payloads)
├── reports/                       # Audit reports (evaluation outputs)
│
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- An Azure OpenAI deployment (model with chat completions support)
- A `.env` file in the project root with:

```env
ENDPOINT_URL=https://<your-resource>.openai.azure.com/
DEPLOYMENT_NAME=<your-deployment>
AZURE_OPENAI_API_KEY=<your-api-key>
```

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Run the pipeline

From the project root:

```powershell
.\tools\run_chronicle.ps1
```

Or directly via the CLI:

```powershell
python -m chronicle --raw-dir raw/meetings/2026
```

Run `python -m chronicle --help` for all available options.

### Run the tests

```powershell
pip install -r requirements-dev.txt
pytest -q
```

---

## How it works

### Compilation Phase

For each raw artifact file in `raw/meetings/2026/` (processed in alphabetical order):

1. **Library Director** reads the artifact and calls Azure OpenAI in Planning Mode, producing a JSON plan that identifies which compiled files are affected.
2. The plan is saved to `out/plan.json`.
3. For each affected compiled file, the appropriate specialist is dispatched:
   - **Librarian Decision Logger** (if `decision-log.md` is targeted):
     - Reads the plan and raw artifact; calls Azure OpenAI in Compilation Mode.
     - Produces structured decision entries as JSON (saved to `out/decisionlog_payload.json`).
     - Inserts entries at the top of `compiled/decision-log.md` (reverse chronological order).
   - **Librarian Glossary Curator** (if `glossary.md` is targeted):
     - Reads the plan and raw artifact; calls Azure OpenAI in Compilation Mode.
     - Produces structured glossary term entries as JSON (saved to `out/glossary_payload.json`).
     - Appends entries to `compiled/glossary.md`.
4. Token usage is appended to `tools/tokens_usage.log`.

### Evaluation Phase

After each batch of compilation (controlled via `--audit-every N` flag), the **Auditor** evaluates the compiled knowledge base:

1. **Deterministic Checks** (5 structural validations, no LLM required):
   - Duplicate DEC IDs in decision log
   - Malformed DEC ID format
   - Missing `### References` section in decision entries
   - Missing `**Introduced in:**` metadata in glossary entries
   - Duplicate glossary term headings (case-insensitive)

2. **Semantic Checks** (via LLM):
   - **Glossary semantic near-duplicates**: Identifies glossary terms that describe the same concept under different names.
   - **Decision semantic near-duplicates**: Identifies decision entries that record essentially the same decision.

3. An **audit report** is generated (Markdown) with findings grouped by severity (errors, warnings, notices) and token metrics, saved to `reports/audit-report-YYYY-MM-DD-###.md`.

---

## Design principles

- **Separation of concerns** — each agent has a single, well-defined responsibility: Library Director plans, specialists compile, Auditor evaluates.
- **Dependency injection** — the LLM client is injected into agents; tests use a fake client with no network calls.
- **Structural guardrails** — schema templates in `schema/` are read-only and govern all compiled output format and structure.
- **Traceability** — every compiled entry references its raw source via the `**Introduced in:**` metadata field.
- **Continuous evaluation** — the Auditor provides deterministic + semantic quality checks after every batch, surfacing issues without blocking the pipeline.
- **Extensibility** — future specialist agents plug into `ChroniclePipeline.register_specialist()` without modifying core logic; new deterministic checks can be added to `chronicle.audit.checks` independently.

