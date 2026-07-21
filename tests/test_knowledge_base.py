import pytest
from chronicle.io.knowledge_base import (
    insert_at_top,
    next_dec_sequence,
    reverse_decision_entries,
)


# ---------------------------------------------------------------------------
# next_dec_sequence
# ---------------------------------------------------------------------------

def test_next_dec_sequence_returns_1_for_missing_file(tmp_path):
    missing = tmp_path / "decision-log.md"
    assert next_dec_sequence(str(missing)) == 1


def test_next_dec_sequence_returns_1_for_empty_file(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text("", encoding="utf-8")
    assert next_dec_sequence(str(log)) == 1


def test_next_dec_sequence_returns_1_when_no_dec_ids(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text("# Decision Log\n\nNo entries yet.\n", encoding="utf-8")
    assert next_dec_sequence(str(log)) == 1


def test_next_dec_sequence_finds_highest_seq(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text(
        "## DEC-2026-01-08-001 — First\n\n## DEC-2026-01-08-002 — Second\n",
        encoding="utf-8",
    )
    assert next_dec_sequence(str(log)) == 3


def test_next_dec_sequence_handles_non_sequential_ids(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text(
        "## DEC-2026-01-08-001 — A\n\n## DEC-2026-02-15-005 — B\n",
        encoding="utf-8",
    )
    assert next_dec_sequence(str(log)) == 6


# ---------------------------------------------------------------------------
# insert_at_top
# ---------------------------------------------------------------------------

def test_insert_at_top_into_empty_file(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text("", encoding="utf-8")
    insert_at_top(str(log), "## DEC-2026-01-08-001 — First\n\ncontent\n")
    assert "DEC-2026-01-08-001" in log.read_text(encoding="utf-8")


def test_insert_at_top_places_entry_after_h1_heading(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text("# Decision Log\n\n## Old Entry\n\nold content\n", encoding="utf-8")
    insert_at_top(str(log), "## DEC-2026-01-08-001 — New\n\nnew content\n")
    result = log.read_text(encoding="utf-8")
    lines = result.splitlines()
    assert lines[0] == "# Decision Log"
    new_idx = next(i for i, line in enumerate(lines) if "DEC-2026-01-08-001" in line)
    old_idx = next(i for i, line in enumerate(lines) if "Old Entry" in line)
    assert new_idx < old_idx


def test_insert_at_top_preserves_existing_content(tmp_path):
    log = tmp_path / "decision-log.md"
    log.write_text("# Decision Log\n\n## Existing\n\nkeep this\n", encoding="utf-8")
    insert_at_top(str(log), "## DEC-2026-01-08-001 — New\n\nnew\n")
    result = log.read_text(encoding="utf-8")
    assert "keep this" in result
    assert "DEC-2026-01-08-001" in result


def test_insert_at_top_creates_missing_parent_dirs(tmp_path):
    nested = tmp_path / "sub" / "deep" / "decision-log.md"
    insert_at_top(str(nested), "## DEC-2026-01-08-001 — Test\n\ncontent\n")
    assert nested.exists()


# ---------------------------------------------------------------------------
# reverse_decision_entries
# ---------------------------------------------------------------------------

def test_reverse_decision_entries_reverses_two_entries():
    md = (
        "## DEC-2026-01-08-001 — First\n"
        "content A\n\n"
        "## DEC-2026-01-08-002 — Second\n"
        "content B\n"
    )
    result = reverse_decision_entries(md)
    idx_002 = result.index("DEC-2026-01-08-002")
    idx_001 = result.index("DEC-2026-01-08-001")
    assert idx_002 < idx_001


def test_reverse_decision_entries_preserves_all_content():
    md = (
        "## DEC-2026-01-08-001 — First\n"
        "content A\n\n"
        "## DEC-2026-01-08-002 — Second\n"
        "content B\n"
    )
    result = reverse_decision_entries(md)
    assert "content A" in result
    assert "content B" in result


def test_reverse_decision_entries_single_entry_returns_same_content():
    md = "## DEC-2026-01-08-001 — Only\ncontent\n"
    result = reverse_decision_entries(md)
    assert "DEC-2026-01-08-001" in result
    assert "content" in result


def test_reverse_decision_entries_no_dec_headings_unchanged():
    md = "No decisions here.\nJust plain text.\n"
    assert reverse_decision_entries(md) == md


def test_reverse_decision_entries_separates_entries_with_blank_line():
    md = (
        "## DEC-2026-01-08-001 — First\ncontent A\n\n"
        "## DEC-2026-01-08-002 — Second\ncontent B\n"
    )
    result = reverse_decision_entries(md)
    assert "\n\n" in result
