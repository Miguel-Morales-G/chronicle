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
