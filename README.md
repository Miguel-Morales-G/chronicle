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

```
Library Director  (Orchestrator Agent)
│
├── Librarian Decision Logger    [Active]
├── Librarian Risk Curator       [Future]
├── Librarian Status Keeper      [Future]
├── Librarian Change Historian   [Future]
├── Librarian Glossary Curator   [Future]
└── Librarian Question Tracker   [Future]
```

- **Library Director** — Analyzes a raw artifact and produces a JSON execution plan. Decides which specialist librarian agents to invoke. Does not write to `compiled/` directly.
- **Librarian Decision Logger** — Extracts decisions from the raw artifact and writes structured entries to `compiled/decision-log.md`, following the schema in `schema/compiled-templates/`.

Chronicle is designed to be **storage-compatible**: compiled knowledge is stored as plain Markdown files in the local filesystem and is compatible with version control, but the system does not depend on any specific storage backend.

---

## Repository Structure

```
chronicle/
├── agents/                        # Agent definitions / system prompts
│   ├── library-director.md
│   └── librarian-decision-logger.md
│
├── compiled/                      # Shared external memory / knowledge base
│   └── decision-log.md
│
├── raw/                           # Artifact / input layer (read-only)
│   └── meetings/
│
├── schema/                        # Structural guardrails
│   ├── cross-file-consistency.md
│   └── compiled-templates/
│       ├── decision-log.md
│       └── ...
│
├── src/chronicle/                 # Agent harness (Python package)
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── library_director.py
│   │   └── librarian_decision_logger.py
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
├── tests/                         # Unit test suite
├── out/                           # Intermediate artifacts (plan.json, payloads)
├── reports/                       # Evaluation outputs
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

For each raw artifact file in `raw/meetings/2026/` (processed in alphabetical order):

1. **Library Director** reads the artifact and calls Azure OpenAI in Planning Mode, producing a JSON plan that identifies which compiled files are affected.
2. The plan is saved to `out/plan.json`.
3. If the plan targets `compiled/decision-log.md` with an `append` operation:
   - **Librarian Decision Logger** reads the plan and the raw artifact, calls Azure OpenAI in Compilation Mode, and produces structured decision entries as JSON.
   - The payload is saved to `out/decisionlog_payload.json`.
   - New entries are inserted at the top of `compiled/decision-log.md` (reverse chronological order).
4. Token usage is appended to `tools/tokens_usage.log`.

---

## Design principles

- **Separation of concerns** — each agent has a single, well-defined responsibility.
- **Dependency injection** — the LLM client is injected into agents; tests use a fake client with no network calls.
- **Structural guardrails** — schema templates in `schema/` are read-only and govern all compiled output.
- **Traceability** — every compiled entry references its raw source.
- **Extensibility** — future specialist agents plug into `ChroniclePipeline.register_specialist()` without modifying core logic.

