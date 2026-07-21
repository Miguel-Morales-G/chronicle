"""Tests for chronicle.audit.checks — deterministic structural checks."""

import pytest
from chronicle.audit.checks import (
    Finding,
    compress_decisions_for_audit,
    count_dec_entries,
    count_glossary_terms,
    find_decisions_missing_references,
    find_duplicate_dec_ids,
    find_duplicate_glossary_headings,
    find_glossary_missing_introduced_in,
    find_malformed_dec_ids,
    run_all_checks,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_GOOD_DECISION_LOG = """\
# Decision Log

## DEC-2026-07-21-001 — Use Python

- **Status:** Accepted
- **Decision date:** 2026-07-21
- **Owner:** Team

### Context
We needed a scripting language.

### Decision
Use Python.

### Rationale
- Widely known.

### Alternatives considered
- Ruby — less popular in team.

### Consequences / Impact
- Faster onboarding.

### References
- `raw/meetings/2026/kickoff.md`
"""

_GOOD_GLOSSARY = """\
# Glossary

## Chronicle

- **Category:** technical
- **Introduced in:** `raw/meetings/2026/kickoff.md`
- **Aliases:** Project Memory

A multi-agent LLM system for continuous project knowledge compilation.

## Pipeline

- **Category:** technical
- **Introduced in:** `raw/meetings/2026/kickoff.md`

The ordered sequence of agents that processes a raw artifact.
"""


# ── find_duplicate_dec_ids ────────────────────────────────────────────────────

def test_find_duplicate_dec_ids_clean():
    findings = find_duplicate_dec_ids(_GOOD_DECISION_LOG)
    assert findings == []


def test_find_duplicate_dec_ids_with_duplicate():
    text = (
        "## DEC-2026-07-21-001 — First\n\n### References\n- `raw/a.md`\n\n"
        "## DEC-2026-07-21-001 — Duplicate\n\n### References\n- `raw/b.md`\n"
    )
    findings = find_duplicate_dec_ids(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "error"
    assert f.check == "duplicate-dec-id"
    assert "DEC-2026-07-21-001" in f.location
    assert "2 times" in f.detail


def test_find_duplicate_dec_ids_distinct_ids_not_flagged():
    text = (
        "## DEC-2026-07-21-001 — First\n\n### References\n- `raw/a.md`\n\n"
        "## DEC-2026-07-21-002 — Second\n\n### References\n- `raw/b.md`\n"
    )
    findings = find_duplicate_dec_ids(text)
    assert findings == []


# ── find_malformed_dec_ids ────────────────────────────────────────────────────

def test_find_malformed_dec_ids_clean():
    findings = find_malformed_dec_ids(_GOOD_DECISION_LOG)
    assert findings == []


def test_find_malformed_dec_ids_with_bad_id():
    text = "## DEC-26-07-21-001 — Short year\n\nSome content.\n"
    findings = find_malformed_dec_ids(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "error"
    assert f.check == "malformed-dec-id"
    assert "DEC-26-07-21-001" in f.location


def test_find_malformed_dec_ids_no_seq_flagged():
    text = "Referenced DEC-2026-07-21 somewhere in the body.\n"
    findings = find_malformed_dec_ids(text)
    assert len(findings) == 1
    assert "DEC-2026-07-21" in findings[0].detail


def test_find_malformed_dec_ids_deduplicates_same_bad_token():
    """The same malformed token appearing twice produces only one Finding."""
    text = "DEC-BAD — one\n\nDEC-BAD — two\n"
    findings = find_malformed_dec_ids(text)
    assert len(findings) == 1


# ── find_decisions_missing_references ────────────────────────────────────────

def test_find_decisions_missing_references_clean():
    findings = find_decisions_missing_references(_GOOD_DECISION_LOG)
    assert findings == []


def test_find_decisions_missing_references_missing():
    text = (
        "## DEC-2026-07-21-001 — No References\n\n"
        "- **Status:** Accepted\n\n"
        "### Context\nDecision context.\n\n"
        "### Decision\nDo something.\n"
    )
    findings = find_decisions_missing_references(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "warning"
    assert f.check == "decision-missing-references"
    assert "DEC-2026-07-21-001" in f.location


def test_find_decisions_missing_references_only_checks_dec_headings():
    """Non-DEC level-2 headings are not checked for References."""
    text = "## Some Other Section\n\nContent without references.\n"
    findings = find_decisions_missing_references(text)
    assert findings == []


# ── find_glossary_missing_introduced_in ──────────────────────────────────────

def test_find_glossary_missing_introduced_in_clean():
    findings = find_glossary_missing_introduced_in(_GOOD_GLOSSARY)
    assert findings == []


def test_find_glossary_missing_introduced_in_missing():
    text = (
        "## Chronicle\n\n"
        "- **Category:** technical\n\n"
        "A multi-agent LLM system.\n"
    )
    findings = find_glossary_missing_introduced_in(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "warning"
    assert f.check == "glossary-missing-introduced-in"
    assert "Chronicle" in f.location


def test_find_glossary_missing_introduced_in_partial():
    """Only the term missing the field is flagged, not others."""
    text = (
        "## TermA\n\n- **Introduced in:** `raw/a.md`\n\nDef A.\n\n"
        "## TermB\n\n- **Category:** technical\n\nDef B.\n"
    )
    findings = find_glossary_missing_introduced_in(text)
    assert len(findings) == 1
    assert "TermB" in findings[0].location


# ── find_duplicate_glossary_headings ─────────────────────────────────────────

def test_find_duplicate_glossary_headings_clean():
    findings = find_duplicate_glossary_headings(_GOOD_GLOSSARY)
    assert findings == []


def test_find_duplicate_glossary_headings_exact_match():
    text = "## Chronicle\n\nDef A.\n\n## Chronicle\n\nDef B.\n"
    findings = find_duplicate_glossary_headings(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "error"
    assert f.check == "duplicate-glossary-heading"
    assert "Chronicle" in f.location


def test_find_duplicate_glossary_headings_case_insensitive():
    text = "## Pipeline\n\nDef A.\n\n## pipeline\n\nDef B.\n"
    findings = find_duplicate_glossary_headings(text)
    assert len(findings) == 1


# ── count helpers ─────────────────────────────────────────────────────────────

def test_count_dec_entries_empty():
    assert count_dec_entries("") == 0


def test_count_dec_entries_finds_headings():
    assert count_dec_entries(_GOOD_DECISION_LOG) == 1


def test_count_glossary_terms_empty():
    assert count_glossary_terms("") == 0


def test_count_glossary_terms_finds_headings():
    assert count_glossary_terms(_GOOD_GLOSSARY) == 2


# ── run_all_checks ────────────────────────────────────────────────────────────

def test_run_all_checks_clean_returns_empty():
    findings = run_all_checks(_GOOD_DECISION_LOG, _GOOD_GLOSSARY)
    assert findings == []


def test_run_all_checks_returns_combined_findings():
    bad_log = "## DEC-BAD — Malformed\n\nNo references section.\n"
    bad_glossary = "## Term\n\n- **Category:** technical\n\nNo introduced-in.\n"
    findings = run_all_checks(bad_log, bad_glossary)
    checks = {f.check for f in findings}
    assert "malformed-dec-id" in checks
    assert "decision-missing-references" in checks
    assert "glossary-missing-introduced-in" in checks


def test_run_all_checks_empty_inputs_returns_empty():
    assert run_all_checks("", "") == []


# ── compress_decisions_for_audit ─────────────────────────────────────────────

_SINGLE_DEC_ENTRY = """\
## DEC-2026-07-21-001 — Use Python

- **Status:** Accepted
- **Decision date:** 2026-07-21
- **Owner:** Team

### Context
We needed a scripting language.

### Decision
Use Python.

### Rationale
- Widely known.

### References
- `raw/meetings/2026/kickoff.md`
"""

_TWO_DEC_ENTRIES = _SINGLE_DEC_ENTRY + """\
## DEC-2026-07-21-002 — Use pytest

- **Status:** Accepted
- **Decision date:** 2026-07-21
- **Owner:** Team

### Context
We needed a test framework.

### Decision
Use pytest for all unit tests.

### Rationale
- Best in class.

### References
- `raw/meetings/2026/kickoff.md`
"""


def test_compress_decisions_empty_string():
    assert compress_decisions_for_audit("") == ""


def test_compress_decisions_whitespace_only():
    assert compress_decisions_for_audit("   \n  ") == ""


def test_compress_decisions_single_entry_one_line():
    result = compress_decisions_for_audit(_SINGLE_DEC_ENTRY)
    lines = result.splitlines()
    assert len(lines) == 1


def test_compress_decisions_single_entry_contains_id_and_title():
    result = compress_decisions_for_audit(_SINGLE_DEC_ENTRY)
    assert "`DEC-2026-07-21-001`" in result
    assert "Use Python" in result


def test_compress_decisions_single_entry_contains_decision_sentence():
    result = compress_decisions_for_audit(_SINGLE_DEC_ENTRY)
    assert "Use Python." in result


def test_compress_decisions_single_entry_contains_date():
    result = compress_decisions_for_audit(_SINGLE_DEC_ENTRY)
    assert "2026-07-21" in result


def test_compress_decisions_two_entries_two_lines():
    result = compress_decisions_for_audit(_TWO_DEC_ENTRIES)
    lines = result.splitlines()
    assert len(lines) == 2
    assert "`DEC-2026-07-21-001`" in lines[0]
    assert "`DEC-2026-07-21-002`" in lines[1]


def test_compress_decisions_missing_decision_section_shows_unavailable():
    entry = """\
## DEC-2026-07-21-003 — A Decision

- **Decision date:** 2026-07-22
- **Status:** Accepted

### References
- `raw/x.md`
"""
    result = compress_decisions_for_audit(entry)
    assert "[unavailable]" in result


def test_compress_decisions_skips_non_dec_headings():
    text = "# Decision Log\n\nSome intro text.\n" + _SINGLE_DEC_ENTRY
    result = compress_decisions_for_audit(text)
    lines = result.splitlines()
    # Only the DEC entry should produce a line.
    assert len(lines) == 1
    assert "`DEC-2026-07-21-001`" in lines[0]
