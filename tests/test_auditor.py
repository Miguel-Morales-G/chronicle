"""Tests for chronicle.audit.auditor — Auditor agent class."""

import json

import pytest
from conftest import FakeLLMClient

from chronicle.audit.auditor import Auditor
from chronicle.io.json_utils import ChronicleJsonError


_GLOSSARY_TEXT = """\
# Glossary

## Chronicle

- **Category:** technical
- **Introduced in:** `raw/meetings/2026/kickoff.md`

A multi-agent LLM system.

## Project Memory

- **Category:** technical
- **Introduced in:** `raw/meetings/2026/kickoff.md`

Earlier name for the Chronicle system.
"""

_SEMANTIC_RESPONSE = json.dumps({
    "semantic_findings": [
        {
            "location": "compiled/glossary.md — Chronicle / Project Memory",
            "detail": "Both terms appear to refer to the same multi-agent system.",
            "recommendation": "Merge into one entry or add an Aliases cross-reference.",
        }
    ]
})

_EMPTY_RESPONSE = json.dumps({"semantic_findings": []})


@pytest.fixture
def auditor_md(tmp_path):
    """Write a minimal auditor system-prompt file and return its path."""
    p = tmp_path / "auditor.md"
    p.write_text("You are the Auditor.", encoding="utf-8")
    return str(p)


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_auditor_returns_empty_list_for_empty_glossary(auditor_md):
    """No LLM call should be made when glossary is empty."""
    client = FakeLLMClient(responses=[])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    findings = auditor.run("")
    assert findings == []
    assert client.calls == []  # no LLM call


def test_auditor_returns_empty_list_for_whitespace_glossary(auditor_md):
    client = FakeLLMClient(responses=[])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    findings = auditor.run("   \n  ")
    assert findings == []


def test_auditor_returns_findings_from_llm_response(auditor_md):
    client = FakeLLMClient(responses=[_SEMANTIC_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    findings = auditor.run(_GLOSSARY_TEXT)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "notice"
    assert f.check == "glossary-semantic-duplicates"
    assert "Chronicle" in f.location
    assert "Project Memory" in f.location


def test_auditor_returns_empty_list_when_no_findings(auditor_md):
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    findings = auditor.run(_GLOSSARY_TEXT)
    assert findings == []


def test_auditor_stores_llm_token_counts_after_run(auditor_md):
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT)
    assert auditor._last_llm_tokens is not None
    prompt_tokens, completion_tokens = auditor._last_llm_tokens
    assert prompt_tokens == 10   # FakeLLMClient returns 10 prompt tokens
    assert completion_tokens == 5


def test_auditor_resets_token_counts_on_empty_glossary(auditor_md):
    """_last_llm_tokens is None after a run with empty glossary."""
    client = FakeLLMClient(responses=[])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    # Simulate a previous run that set tokens
    auditor._last_llm_tokens = (99, 88)
    auditor.run("")  # empty → resets
    assert auditor._last_llm_tokens is None


# ── Prompt content tests ──────────────────────────────────────────────────────

def test_auditor_prompt_includes_glossary_text(auditor_md):
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT)
    user_prompt = client.calls[0]["user_prompt"]
    assert "Chronicle" in user_prompt
    assert "Project Memory" in user_prompt


def test_auditor_prompt_instructs_no_invented_findings(auditor_md):
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT)
    user_prompt = client.calls[0]["user_prompt"]
    assert "NOT invent" in user_prompt or "Do NOT invent" in user_prompt


# ── Error-handling tests ──────────────────────────────────────────────────────

def test_auditor_raises_chronicle_json_error_on_bad_json(auditor_md):
    client = FakeLLMClient(responses=["this is not json"])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    with pytest.raises(ChronicleJsonError):
        auditor.run(_GLOSSARY_TEXT)


# ── Decision near-duplicate tests ──────────────────────────────────────────────

_TWO_ENTRY_DECISION_LOG = """\
## DEC-2026-07-21-001 — Use Python

- **Status:** Accepted
- **Decision date:** 2026-07-21

### Decision
Use Python.

### References
- `raw/meetings/2026/kickoff.md`

## DEC-2026-07-21-002 — Choose Python as Language

- **Status:** Accepted
- **Decision date:** 2026-07-21

### Decision
Adopt Python as the primary language.

### References
- `raw/meetings/2026/kickoff.md`
"""

_DECISION_SEMANTIC_RESPONSE = json.dumps({
    "semantic_findings": [
        {
            "location": "compiled/decision-log.md — DEC-2026-07-21-001 / DEC-2026-07-21-002",
            "detail": "Both entries choose Python as the project language.",
            "recommendation": "Consolidate into a single decision entry.",
        }
    ]
})


def test_auditor_no_decision_call_when_decision_log_empty(auditor_md):
    """No decision LLM call when decision_log_text is empty."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text="")
    # Only the glossary call should have been made.
    assert len(client.calls) == 1
    assert auditor._last_llm_call_count == 1


def test_auditor_no_decision_call_for_single_entry(auditor_md):
    """Single decision entry (no newline in compressed) → skip decision check."""
    single_entry = (
        "## DEC-2026-07-21-001 — Use Python\n"
        "- **Decision date:** 2026-07-21\n"
        "### Decision\nUse Python.\n"
        "### References\n- `raw/x.md`\n"
    )
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text=single_entry)
    assert len(client.calls) == 1
    assert auditor._last_llm_call_count == 1


def test_auditor_decision_findings_returned(auditor_md):
    """Decision near-duplicate findings are returned with correct check name."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE, _DECISION_SEMANTIC_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    findings = auditor.run(_GLOSSARY_TEXT, decision_log_text=_TWO_ENTRY_DECISION_LOG)
    decision_findings = [f for f in findings if f.check == "decision-semantic-duplicates"]
    assert len(decision_findings) == 1
    f = decision_findings[0]
    assert f.severity == "notice"
    assert "DEC-2026-07-21-001" in f.location
    assert "DEC-2026-07-21-002" in f.location


def test_auditor_decision_prompt_includes_compressed_entries(auditor_md):
    """The second LLM prompt contains the compressed decision lines."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE, _EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text=_TWO_ENTRY_DECISION_LOG)
    decision_prompt = client.calls[1]["user_prompt"]
    assert "DEC-2026-07-21-001" in decision_prompt
    assert "DEC-2026-07-21-002" in decision_prompt
    assert "Use Python" in decision_prompt


def test_auditor_two_calls_when_both_inputs_provided(auditor_md):
    """_last_llm_call_count is 2 when both glossary and decision log are non-empty."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE, _EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text=_TWO_ENTRY_DECISION_LOG)
    assert auditor._last_llm_call_count == 2
    assert len(client.calls) == 2


def test_auditor_token_totals_accumulated_across_both_calls(auditor_md):
    """Tokens from both calls are summed in _last_llm_tokens."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE, _EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text=_TWO_ENTRY_DECISION_LOG)
    assert auditor._last_llm_tokens is not None
    prompt_total, completion_total = auditor._last_llm_tokens
    # FakeLLMClient returns 10 prompt + 5 completion per call; 2 calls = 20 + 10
    assert prompt_total == 20
    assert completion_total == 10


def test_auditor_call_count_zero_when_both_empty(auditor_md):
    """No calls and _last_llm_tokens is None when both inputs are empty."""
    client = FakeLLMClient(responses=[])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run("", decision_log_text="")
    assert auditor._last_llm_call_count == 0
    assert auditor._last_llm_tokens is None


def test_auditor_call_count_one_when_only_glossary_provided(auditor_md):
    """_last_llm_call_count is 1 when only the glossary is non-empty."""
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text="")
    assert auditor._last_llm_call_count == 1


def test_auditor_decision_prompt_instructs_no_invented_findings(auditor_md):
    client = FakeLLMClient(responses=[_EMPTY_RESPONSE, _EMPTY_RESPONSE])
    auditor = Auditor(name="Auditor", system_prompt_path=auditor_md, llm_client=client)
    auditor.run(_GLOSSARY_TEXT, decision_log_text=_TWO_ENTRY_DECISION_LOG)
    decision_prompt = client.calls[1]["user_prompt"]
    assert "Do NOT invent" in decision_prompt
