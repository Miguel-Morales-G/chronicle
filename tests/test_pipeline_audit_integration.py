"""Tests for Chronicle pipeline integration with the Auditor.

Verifies that the Auditor is triggered at the correct intervals during
``process_directory``, that reports are written to the correct location,
and that the pipeline functions correctly without an Auditor.
"""

import json
from pathlib import Path

import pytest
from conftest import FakeLLMClient

from chronicle.agents.librarian_decision_logger import LibrarianDecisionLogger
from chronicle.agents.library_director import LibraryDirector
from chronicle.audit.auditor import Auditor
from chronicle.pipeline.chronicle_pipeline import ChroniclePipeline


# ── Fake LLM responses ────────────────────────────────────────────────────────

# Library Director returns an empty plan (no specialist needed) so the file
# is skipped.  This lets us test audit-trigger counts without managing
# decision-log or glossary compilation state.
_SKIP_PLAN = json.dumps({"affected_files": []})

# Auditor LLM response — no semantic findings.
_AUDIT_RESPONSE = json.dumps({"semantic_findings": []})


# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
def env(tmp_path):
    """Minimal on-disk environment for pipeline + audit integration tests."""
    raw_dir = tmp_path / "raw" / "meetings" / "2026"
    raw_dir.mkdir(parents=True)
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    schema_dir = tmp_path / "schema" / "compiled-templates"
    schema_dir.mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    # Agent system-prompt stubs
    (agents_dir / "library-director.md").write_text(
        "You are the Library Director.", encoding="utf-8"
    )
    (agents_dir / "librarian-decision-logger.md").write_text(
        "You are the Decision Logger.", encoding="utf-8"
    )
    (agents_dir / "auditor.md").write_text(
        "You are the Auditor.", encoding="utf-8"
    )

    # Schema template stub
    (schema_dir / "decision-log.md").write_text(
        "## DEC-YYYY-MM-DD-### — <Title>", encoding="utf-8"
    )

    # One default raw file
    raw_file = raw_dir / "test-meeting.md"
    raw_file.write_text("# Test Meeting\n\nNothing to compile.", encoding="utf-8")

    return {
        "raw_dir": raw_dir,
        "compiled_dir": compiled_dir,
        "agents_dir": agents_dir,
        "schema_dir": schema_dir.parent,  # schema/ root, not compiled-templates/
        "out_dir": out_dir,
        "reports_dir": reports_dir,
        "raw_file": raw_file,
        "tmp_path": tmp_path,
    }


def _add_raw_files(env: dict, n: int) -> None:
    """Create *n* additional raw .md files in the raw_dir."""
    for i in range(1, n + 1):
        f = env["raw_dir"] / f"meeting-{i:02d}.md"
        f.write_text(f"# Meeting {i}\n\nNothing to compile.", encoding="utf-8")


def _make_pipeline(
    env: dict,
    n_files: int = 1,
    audit_every: int = 5,
    audit_now: bool = False,
    with_auditor: bool = True,
) -> ChroniclePipeline:
    """Build a ChroniclePipeline with FakeLLMClients for all agents."""
    if n_files > 1:
        _add_raw_files(env, n_files - 1)

    # Director needs one response per file; Auditor needs one per audit run.
    n_audit_runs = (n_files // audit_every) + 2 if audit_every > 0 else 2
    plan_responses = [_SKIP_PLAN] * n_files
    audit_responses = [_AUDIT_RESPONSE] * n_audit_runs

    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(env["agents_dir"] / "library-director.md"),
        llm_client=FakeLLMClient(responses=plan_responses),
    )
    decision_logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(env["agents_dir"] / "librarian-decision-logger.md"),
        llm_client=FakeLLMClient(responses=[]),
    )
    auditor = (
        Auditor(
            name="Auditor",
            system_prompt_path=str(env["agents_dir"] / "auditor.md"),
            llm_client=FakeLLMClient(responses=audit_responses),
        )
        if with_auditor
        else None
    )

    return ChroniclePipeline(
        director=director,
        decision_logger=decision_logger,
        compiled_dir=env["compiled_dir"],
        schema_dir=env["schema_dir"],
        out_dir=env["out_dir"],
        auditor=auditor,
        audit_every=audit_every,
        audit_now=audit_now,
        reports_dir=env["reports_dir"],
    )


def _report_count(env: dict) -> int:
    return len(list(env["reports_dir"].glob("audit-report-*.md")))


# ── Trigger tests ─────────────────────────────────────────────────────────────

def test_audit_runs_at_end_of_run_for_single_file(env):
    """1 file + audit_every=5 → final audit runs → 1 report."""
    pipeline = _make_pipeline(env, n_files=1, audit_every=5)
    pipeline.process_directory(env["raw_dir"])
    assert _report_count(env) == 1


def test_audit_triggers_mid_loop_at_n_files(env):
    """5 files + audit_every=5 → periodic trigger at file 5 → 1 report, no final."""
    pipeline = _make_pipeline(env, n_files=5, audit_every=5)
    pipeline.process_directory(env["raw_dir"])
    assert _report_count(env) == 1


def test_audit_runs_twice_for_ten_files(env):
    """10 files + audit_every=5 → triggers at file 5 and file 10 → 2 reports."""
    pipeline = _make_pipeline(env, n_files=10, audit_every=5)
    pipeline.process_directory(env["raw_dir"])
    assert _report_count(env) == 2


def test_audit_now_forces_end_of_run_audit(env):
    """audit_now=True forces a final audit even with a very high audit_every."""
    pipeline = _make_pipeline(env, n_files=1, audit_every=100, audit_now=True)
    pipeline.process_directory(env["raw_dir"])
    assert _report_count(env) == 1


def test_audit_every_zero_disables_periodic_trigger(env):
    """audit_every=0 suppresses the periodic trigger; only end-of-run applies."""
    pipeline = _make_pipeline(env, n_files=3, audit_every=0)
    pipeline.process_directory(env["raw_dir"])
    # With audit_every=0, periodic trigger never fires; end-of-run still fires
    # (processed_since_audit=3 > 0).
    assert _report_count(env) == 1


def test_no_audit_without_auditor(env):
    """Pipeline without an Auditor produces no reports."""
    pipeline = _make_pipeline(env, with_auditor=False)
    pipeline.process_directory(env["raw_dir"])
    assert _report_count(env) == 0


# ── Output location / content tests ──────────────────────────────────────────

def test_audit_report_written_to_reports_dir(env):
    pipeline = _make_pipeline(env)
    pipeline.process_directory(env["raw_dir"])
    reports = list(env["reports_dir"].glob("audit-report-*.md"))
    assert len(reports) == 1
    assert reports[0].parent == env["reports_dir"]


def test_audit_report_filename_format(env):
    pipeline = _make_pipeline(env)
    pipeline.process_directory(env["raw_dir"])
    report = next(env["reports_dir"].glob("audit-report-*.md"))
    import re
    assert re.match(r"audit-report-\d{4}-\d{2}-\d{2}-\d{3}\.md", report.name)


def test_audit_report_contains_required_sections(env):
    pipeline = _make_pipeline(env)
    pipeline.process_directory(env["raw_dir"])
    report = next(env["reports_dir"].glob("audit-report-*.md"))
    content = report.read_text(encoding="utf-8")
    assert "# Chronicle Audit Report" in content
    assert "## Summary" in content
    assert "## Findings" in content
    assert "## Metrics" in content
    assert "## Report Meta" in content


def test_sequential_reports_get_sequential_numbers(env):
    """Two audit runs on the same day produce -001 and -002."""
    pipeline_1 = _make_pipeline(env, n_files=1, audit_every=5)
    pipeline_1.process_directory(env["raw_dir"])

    # Second pipeline run — add a fresh raw file so the directory isn't empty.
    _add_raw_files(env, 1)
    pipeline_2 = _make_pipeline(env, n_files=1, audit_every=5)
    # Reset raw_dir to only the new file for the second run
    pipeline_2.process_directory(env["raw_dir"])

    reports = sorted(env["reports_dir"].glob("audit-report-*.md"))
    assert len(reports) >= 2
    assert reports[0].name.endswith("-001.md")
    assert reports[1].name.endswith("-002.md")
