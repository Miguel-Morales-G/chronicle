"""Tests for chronicle.audit.report — sequence numbering and report rendering."""

from datetime import date
from pathlib import Path

import pytest

from chronicle.audit.checks import Finding
from chronicle.audit.report import (
    next_audit_sequence,
    render_report,
    write_audit_report,
)


# ── next_audit_sequence ───────────────────────────────────────────────────────

def test_next_audit_sequence_missing_dir(tmp_path):
    """Non-existent directory → sequence 1."""
    seq = next_audit_sequence(tmp_path / "nonexistent", date(2026, 7, 21))
    assert seq == 1


def test_next_audit_sequence_empty_dir(tmp_path):
    """Empty directory → sequence 1."""
    seq = next_audit_sequence(tmp_path, date(2026, 7, 21))
    assert seq == 1


def test_next_audit_sequence_single_report(tmp_path):
    (tmp_path / "audit-report-2026-07-21-001.md").write_text("x")
    seq = next_audit_sequence(tmp_path, date(2026, 7, 21))
    assert seq == 2


def test_next_audit_sequence_multiple_reports_same_day(tmp_path):
    (tmp_path / "audit-report-2026-07-21-001.md").write_text("x")
    (tmp_path / "audit-report-2026-07-21-003.md").write_text("x")
    seq = next_audit_sequence(tmp_path, date(2026, 7, 21))
    assert seq == 4


def test_next_audit_sequence_different_date_ignored(tmp_path):
    """Reports from a different date do not affect today's sequence."""
    (tmp_path / "audit-report-2026-07-20-005.md").write_text("x")
    seq = next_audit_sequence(tmp_path, date(2026, 7, 21))
    assert seq == 1


# ── render_report ─────────────────────────────────────────────────────────────

_BASE_METRICS = {
    "date": "2026-07-21",
    "seq": 1,
    "dec_entries": 3,
    "glossary_terms": 5,
    "trigger": "end-of-run",
    "generated_at": "2026-07-21T12:00:00Z",
    "prompt_tokens": None,
    "completion_tokens": None,
}


def test_render_report_ok_status_when_no_findings():
    content = render_report([], [], _BASE_METRICS)
    assert "Overall status:** OK" in content


def test_render_report_warn_status_with_warnings():
    findings = [Finding(
        severity="warning", check="decision-missing-references",
        location="compiled/decision-log.md — ## DEC-2026-07-21-001",
        detail="Missing references.", recommendation="Add references section."
    )]
    content = render_report(findings, [], _BASE_METRICS)
    assert "Overall status:** WARN" in content


def test_render_report_fail_status_with_errors():
    findings = [Finding(
        severity="error", check="duplicate-dec-id",
        location="compiled/decision-log.md — DEC-2026-07-21-001",
        detail="Duplicate.", recommendation="Renumber."
    )]
    content = render_report(findings, [], _BASE_METRICS)
    assert "Overall status:** FAIL" in content


def test_render_report_contains_all_required_sections():
    content = render_report([], [], _BASE_METRICS)
    assert "# Chronicle Audit Report" in content
    assert "## Summary" in content
    assert "## Findings" in content
    assert "## Metrics" in content
    assert "## Report Meta" in content


def test_render_report_includes_report_id():
    content = render_report([], [], _BASE_METRICS)
    assert "2026-07-21-001" in content


def test_render_report_finding_appears_in_output():
    findings = [Finding(
        severity="error", check="duplicate-dec-id",
        location="compiled/decision-log.md — DEC-2026-07-21-001",
        detail="ID appears twice.", recommendation="Renumber later occurrence."
    )]
    content = render_report(findings, [], _BASE_METRICS)
    assert "duplicate-dec-id" in content
    assert "ID appears twice." in content
    assert "Renumber later occurrence." in content


def test_render_report_no_findings_message():
    content = render_report([], [], _BASE_METRICS)
    assert "structurally healthy" in content


def test_render_report_skips_llm_line_when_no_glossary():
    content = render_report([], [], _BASE_METRICS)
    assert "semantic check skipped" in content


def test_render_report_shows_llm_tokens_when_available():
    metrics = {**_BASE_METRICS, "prompt_tokens": 120, "completion_tokens": 45}
    content = render_report([], [], metrics)
    assert "prompt=120" in content
    assert "completion=45" in content


def test_render_report_llm_call_count_line_shows_two_calls():
    """When llm_call_count=2, the report shows 'LLM calls: 2'."""
    metrics = {
        **_BASE_METRICS,
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "llm_call_count": 2,
    }
    content = render_report([], [], metrics)
    assert "LLM calls: 2" in content
    assert "prompt=20" in content
    assert "completion=10" in content


def test_render_report_summary_counts_correct():
    det = [
        Finding("error", "duplicate-dec-id", "loc", "d", "r"),
        Finding("warning", "decision-missing-references", "loc", "d", "r"),
    ]
    sem = [Finding("notice", "glossary-semantic-duplicates", "loc", "d", "r")]
    content = render_report(det, sem, _BASE_METRICS)
    # Summary table values
    assert "| Errors   | 1" in content
    assert "| Warnings | 1" in content
    assert "| Notices  | 1" in content


# ── write_audit_report ────────────────────────────────────────────────────────

def test_write_audit_report_creates_file(tmp_path):
    path = write_audit_report(tmp_path, date(2026, 7, 21), 1, "# Report\n")
    assert path.exists()
    assert path.name == "audit-report-2026-07-21-001.md"


def test_write_audit_report_correct_content(tmp_path):
    content = "# Chronicle Audit Report\n\nAll good.\n"
    path = write_audit_report(tmp_path, date(2026, 7, 21), 2, content)
    assert path.read_text(encoding="utf-8") == content


def test_write_audit_report_creates_parent_dirs(tmp_path):
    nested = tmp_path / "deep" / "reports"
    path = write_audit_report(nested, date(2026, 7, 21), 1, "x")
    assert path.exists()
