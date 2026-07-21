"""
Smoke tests for the ChroniclePipeline.

These tests exercise the full two-step pipeline (Library Director →
Librarian Decision Logger) using FakeLLMClient — no network calls are made.

The tests use monkeypatch.chdir(tmp_path) so that relative raw_refs paths
produced by the fake Library Director response resolve correctly inside
the temporary directory structure.
"""
import json
import pytest
from conftest import FakeLLMClient
from chronicle.agents.librarian_decision_logger import LibrarianDecisionLogger
from chronicle.agents.librarian_glossary_curator import LibrarianGlossaryCurator
from chronicle.agents.library_director import LibraryDirector
from chronicle.pipeline.chronicle_pipeline import ChroniclePipeline


# ---------------------------------------------------------------------------
# Fake LLM responses
# ---------------------------------------------------------------------------

_PLAN_RESPONSE = json.dumps(
    {
        "affected_files": [
            {
                "path": "compiled/decision-log.md",
                "operation": "append",
                "why": "Meeting note contains a decision.",
                "raw_refs": ["raw/meetings/2026/test-meeting.md"],
            }
        ]
    }
)

_PAYLOAD_RESPONSE = json.dumps(
    {
        "append_to": "compiled/decision-log.md",
        "new_entries_markdown": (
            "## DEC-2026-01-08-001 — Use Python\n\n"
            "- **Status:** Accepted\n"
            "- **Decision date:** 2026-01-08\n\n"
            "### References\n"
            "- `raw/meetings/2026/test-meeting.md`\n"
        ),
    }
)

_GLOSSARY_PLAN_RESPONSE = json.dumps(
    {
        "affected_files": [
            {
                "path": "compiled/glossary.md",
                "operation": "additive",
                "why": "Meeting introduces the term Chronicle.",
                "raw_refs": ["raw/meetings/2026/test-meeting.md"],
            }
        ]
    }
)

_GLOSSARY_PAYLOAD_RESPONSE = json.dumps(
    {
        "append_to": "compiled/glossary.md",
        "new_entries_markdown": (
            "## Chronicle\n\n"
            "- **Category:** domain\n"
            "- **Introduced in:** `raw/meetings/2026/test-meeting.md`\n\n"
            "A multi-agent LLM system.\n"
        ),
    }
)

_BOTH_PLAN_RESPONSE = json.dumps(
    {
        "affected_files": [
            {
                "path": "compiled/decision-log.md",
                "operation": "append",
                "why": "Contains a decision.",
                "raw_refs": ["raw/meetings/2026/test-meeting.md"],
            },
            {
                "path": "compiled/glossary.md",
                "operation": "additive",
                "why": "Introduces the term Chronicle.",
                "raw_refs": ["raw/meetings/2026/test-meeting.md"],
            },
        ]
    }
)

@pytest.fixture
def env(tmp_path, monkeypatch):
    """Minimal Chronicle directory tree in a temp directory.

    monkeypatch.chdir ensures that relative paths in raw_refs
    (e.g. 'raw/meetings/2026/test-meeting.md') resolve inside tmp_path.
    """
    monkeypatch.chdir(tmp_path)

    # Raw artifact (must match raw_refs path in _PLAN_RESPONSE)
    raw_dir = tmp_path / "raw" / "meetings" / "2026"
    raw_dir.mkdir(parents=True)
    raw_file = raw_dir / "test-meeting.md"
    raw_file.write_text("# Meeting 2026-01-08\n\nDecided to use Python.", encoding="utf-8")

    # Agent prompt files
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "library-director.md").write_text(
        "You are the Library Director.", encoding="utf-8"
    )
    (agents_dir / "librarian-decision-logger.md").write_text(
        "You are the Decision Logger.", encoding="utf-8"
    )
    (agents_dir / "librarian-glossary-curator.md").write_text(
        "You are the Glossary Curator.", encoding="utf-8"
    )

    # Schema template
    schema_dir = tmp_path / "schema" / "compiled-templates"
    schema_dir.mkdir(parents=True)
    (schema_dir / "decision-log.md").write_text(
        "## DEC-YYYY-MM-DD-### — <Title>", encoding="utf-8"
    )
    (schema_dir / "glossary.md").write_text(
        "## <Term>\n\n- **Introduced in:** `raw/<path>`", encoding="utf-8"
    )

    # Compiled dir (starts empty)
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir()

    out_dir = tmp_path / "out"

    return {
        "raw_file": raw_file,
        "raw_dir": raw_dir,
        "agents_dir": agents_dir,
        "compiled_dir": compiled_dir,
        "schema_dir": tmp_path / "schema",
        "out_dir": out_dir,
    }


def _make_pipeline(env, plan_response=_PLAN_RESPONSE, payload_response=_PAYLOAD_RESPONSE):
    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(env["agents_dir"] / "library-director.md"),
        llm_client=FakeLLMClient(responses=[plan_response]),
    )
    decision_logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(env["agents_dir"] / "librarian-decision-logger.md"),
        llm_client=FakeLLMClient(responses=[payload_response]),
    )
    return ChroniclePipeline(
        director=director,
        decision_logger=decision_logger,
        compiled_dir=env["compiled_dir"],
        schema_dir=env["schema_dir"],
        out_dir=env["out_dir"],
    )


def _make_pipeline_with_glossary(
    env,
    plan_response=_PLAN_RESPONSE,
    payload_response=_PAYLOAD_RESPONSE,
    glossary_response=_GLOSSARY_PAYLOAD_RESPONSE,
):
    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(env["agents_dir"] / "library-director.md"),
        llm_client=FakeLLMClient(responses=[plan_response]),
    )
    decision_logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(env["agents_dir"] / "librarian-decision-logger.md"),
        llm_client=FakeLLMClient(responses=[payload_response]),
    )
    glossary_curator = LibrarianGlossaryCurator(
        name="Librarian Glossary Curator",
        system_prompt_path=str(env["agents_dir"] / "librarian-glossary-curator.md"),
        llm_client=FakeLLMClient(responses=[glossary_response]),
    )
    return ChroniclePipeline(
        director=director,
        decision_logger=decision_logger,
        compiled_dir=env["compiled_dir"],
        schema_dir=env["schema_dir"],
        out_dir=env["out_dir"],
        glossary_curator=glossary_curator,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pipeline_constructed_without_network(env):
    """Pipeline can be constructed and holds agent references — no network calls."""
    pipeline = _make_pipeline(env)
    assert pipeline.director is not None
    assert pipeline.decision_logger is not None


def test_process_file_returns_no_error(env):
    pipeline = _make_pipeline(env)
    result = pipeline.process_file(env["raw_file"])
    assert result.error is None


def test_process_file_not_skipped_for_decision_plan(env):
    pipeline = _make_pipeline(env)
    result = pipeline.process_file(env["raw_file"])
    assert result.skipped is False


def test_process_file_writes_plan_json(env):
    pipeline = _make_pipeline(env)
    pipeline.process_file(env["raw_file"])
    plan_file = env["out_dir"] / "plan.json"
    assert plan_file.exists()
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    assert plan["affected_files"][0]["path"] == "compiled/decision-log.md"


def test_process_file_writes_payload_json(env):
    pipeline = _make_pipeline(env)
    pipeline.process_file(env["raw_file"])
    payload_file = env["out_dir"] / "decisionlog_payload.json"
    assert payload_file.exists()
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    assert "new_entries_markdown" in payload


def test_process_file_inserts_entry_into_compiled(env):
    pipeline = _make_pipeline(env)
    pipeline.process_file(env["raw_file"])
    decision_log = env["compiled_dir"] / "decision-log.md"
    assert decision_log.exists()
    assert "DEC-2026-01-08-001" in decision_log.read_text(encoding="utf-8")


def test_process_file_skips_when_plan_has_no_decision_target(env):
    no_decision_plan = json.dumps({"affected_files": []})
    pipeline = _make_pipeline(env, plan_response=no_decision_plan)
    result = pipeline.process_file(env["raw_file"])
    assert result.skipped is True


def test_process_directory_returns_one_result_per_file(env):
    pipeline = _make_pipeline(env)
    results = pipeline.process_directory(env["raw_dir"])
    assert len(results) == 1


def test_process_directory_empty_dir_returns_empty_list(env):
    pipeline = _make_pipeline(env)
    empty_dir = env["raw_file"].parent.parent / "empty"
    empty_dir.mkdir()
    results = pipeline.process_directory(empty_dir)
    assert results == []


def test_process_directory_continues_past_failed_file(env, tmp_path):
    """Pipeline processes remaining files even when one file causes an error."""
    # Add a second raw file
    second_file = env["raw_dir"] / "zzz-second-meeting.md"
    second_file.write_text("# Second Meeting", encoding="utf-8")

    # Director returns invalid JSON for first call, valid for second
    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(env["agents_dir"] / "library-director.md"),
        llm_client=FakeLLMClient(responses=["not json", _PLAN_RESPONSE]),
    )
    decision_logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(env["agents_dir"] / "librarian-decision-logger.md"),
        llm_client=FakeLLMClient(responses=[_PAYLOAD_RESPONSE]),
    )
    pipeline = ChroniclePipeline(
        director=director,
        decision_logger=decision_logger,
        compiled_dir=env["compiled_dir"],
        schema_dir=env["schema_dir"],
        out_dir=env["out_dir"],
    )
    results = pipeline.process_directory(env["raw_dir"])
    assert len(results) == 2
    # First file errored, second succeeded
    assert results[0].error is not None
    assert results[1].error is None


# ---------------------------------------------------------------------------
# Glossary Curator dispatch tests
# ---------------------------------------------------------------------------

def test_glossary_plan_updates_glossary_file(env):
    pipeline = _make_pipeline_with_glossary(
        env,
        plan_response=_GLOSSARY_PLAN_RESPONSE,
        glossary_response=_GLOSSARY_PAYLOAD_RESPONSE,
    )
    result = pipeline.process_file(env["raw_file"])
    assert result.error is None
    assert not result.skipped
    glossary = env["compiled_dir"] / "glossary.md"
    assert glossary.exists()
    assert "Chronicle" in glossary.read_text(encoding="utf-8")


def test_glossary_plan_does_not_touch_decision_log(env):
    pipeline = _make_pipeline_with_glossary(
        env,
        plan_response=_GLOSSARY_PLAN_RESPONSE,
        glossary_response=_GLOSSARY_PAYLOAD_RESPONSE,
    )
    pipeline.process_file(env["raw_file"])
    decision_log = env["compiled_dir"] / "decision-log.md"
    assert not decision_log.exists()


def test_both_specialists_run_when_plan_targets_both(env):
    """When the plan targets both files, both specialists run."""
    pipeline = _make_pipeline_with_glossary(
        env,
        plan_response=_BOTH_PLAN_RESPONSE,
        payload_response=_PAYLOAD_RESPONSE,
        glossary_response=_GLOSSARY_PAYLOAD_RESPONSE,
    )
    result = pipeline.process_file(env["raw_file"])
    assert result.error is None
    assert "compiled/decision-log.md" in result.payloads
    assert "compiled/glossary.md" in result.payloads
    assert (env["compiled_dir"] / "decision-log.md").exists()
    assert (env["compiled_dir"] / "glossary.md").exists()


def test_unregistered_compiled_path_is_skipped_not_error(env):
    """A plan entry for a future compiled file produces no error — just a skip log."""
    future_plan = json.dumps(
        {
            "affected_files": [
                {
                    "path": "compiled/risks-and-open-questions.md",
                    "operation": "additive",
                    "why": "New risk identified.",
                    "raw_refs": ["raw/meetings/2026/test-meeting.md"],
                }
            ]
        }
    )
    pipeline = _make_pipeline(env, plan_response=future_plan)
    result = pipeline.process_file(env["raw_file"])
    assert result.error is None
    assert result.skipped is True


def test_glossary_payload_json_written_to_out(env):
    pipeline = _make_pipeline_with_glossary(
        env,
        plan_response=_GLOSSARY_PLAN_RESPONSE,
        glossary_response=_GLOSSARY_PAYLOAD_RESPONSE,
    )
    pipeline.process_file(env["raw_file"])
    payload_file = env["out_dir"] / "glossary_payload.json"
    assert payload_file.exists()
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    assert "new_entries_markdown" in data
