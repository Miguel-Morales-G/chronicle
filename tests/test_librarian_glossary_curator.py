import json
import pytest
from conftest import FakeLLMClient
from chronicle.agents.librarian_glossary_curator import (
    GlossaryPayload,
    LibrarianGlossaryCurator,
)
from chronicle.agents.library_director import AffectedFile, Plan
from chronicle.io.json_utils import ChronicleJsonError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = json.dumps(
    {
        "append_to": "compiled/glossary.md",
        "new_entries_markdown": (
            "## Chronicle\n\n"
            "- **Category:** domain\n"
            "- **Introduced in:** `raw/meetings/2026/kickoff.md`\n\n"
            "A multi-agent LLM system for continuous project knowledge compilation.\n"
        ),
    }
)


def _glossary_plan():
    return Plan(
        affected_files=[
            AffectedFile(
                path="compiled/glossary.md",
                operation="additive",
                why="Meeting introduces the term Chronicle.",
                raw_refs=["raw/meetings/2026/kickoff.md"],
            )
        ]
    )


def _make_curator(tmp_path, responses):
    prompt_file = tmp_path / "librarian-glossary-curator.md"
    prompt_file.write_text("You are the Librarian Glossary Curator.", encoding="utf-8")
    client = FakeLLMClient(responses=responses)
    curator = LibrarianGlossaryCurator(
        name="Librarian Glossary Curator",
        system_prompt_path=str(prompt_file),
        llm_client=client,
    )
    return curator, client


from chronicle.agents.librarian_decision_logger import RawInput

_RAW_INPUTS = [RawInput(ref="raw/meetings/2026/kickoff.md", content="# Kickoff\n\nChronicle is our system.")]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_returns_glossary_payload(tmp_path):
    curator, _ = _make_curator(tmp_path, [_VALID_PAYLOAD])
    payload = curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="## <Term>\n\n- **Introduced in:** `raw/<path>`\n",
        existing_terms=[],
    )
    assert isinstance(payload, GlossaryPayload)
    assert payload.append_to == "compiled/glossary.md"
    assert payload.new_entries_markdown != ""


def test_run_payload_contains_term_entry(tmp_path):
    curator, _ = _make_curator(tmp_path, [_VALID_PAYLOAD])
    payload = curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="",
        existing_terms=[],
    )
    assert "## Chronicle" in payload.new_entries_markdown


def test_run_raises_when_plan_has_no_glossary_entry(tmp_path):
    curator, _ = _make_curator(tmp_path, [_VALID_PAYLOAD])
    empty_plan = Plan(affected_files=[])
    with pytest.raises(ValueError, match="requires a plan entry"):
        curator.run(
            plan=empty_plan,
            raw_inputs=_RAW_INPUTS,
            template_text="",
            existing_terms=[],
        )


def test_run_raises_when_response_missing_new_entries_markdown(tmp_path):
    bad_payload = json.dumps({"append_to": "compiled/glossary.md"})
    curator, _ = _make_curator(tmp_path, [bad_payload])
    with pytest.raises(ValueError, match="new_entries_markdown"):
        curator.run(
            plan=_glossary_plan(),
            raw_inputs=_RAW_INPUTS,
            template_text="",
            existing_terms=[],
        )


def test_run_raises_on_invalid_json(tmp_path):
    curator, _ = _make_curator(tmp_path, ["not json"])
    with pytest.raises(ChronicleJsonError):
        curator.run(
            plan=_glossary_plan(),
            raw_inputs=_RAW_INPUTS,
            template_text="",
            existing_terms=[],
        )


def test_prompt_contains_existing_terms(tmp_path):
    curator, client = _make_curator(tmp_path, [_VALID_PAYLOAD])
    curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="template",
        existing_terms=["Pipeline", "Agent"],
    )
    assert "Pipeline" in client.calls[0]["user_prompt"]
    assert "Agent" in client.calls[0]["user_prompt"]


def test_prompt_contains_raw_refs(tmp_path):
    curator, client = _make_curator(tmp_path, [_VALID_PAYLOAD])
    curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="template",
        existing_terms=[],
    )
    assert "raw/meetings/2026/kickoff.md" in client.calls[0]["user_prompt"]


def test_prompt_contains_template_text(tmp_path):
    curator, client = _make_curator(tmp_path, [_VALID_PAYLOAD])
    curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="## UNIQUE_GLOSSARY_TEMPLATE_MARKER",
        existing_terms=[],
    )
    assert "## UNIQUE_GLOSSARY_TEMPLATE_MARKER" in client.calls[0]["user_prompt"]


def test_empty_new_entries_markdown_is_accepted(tmp_path):
    """Model may return empty string when no new terms found — this is valid."""
    empty_payload = json.dumps({"append_to": "compiled/glossary.md", "new_entries_markdown": ""})
    curator, _ = _make_curator(tmp_path, [empty_payload])
    payload = curator.run(
        plan=_glossary_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="",
        existing_terms=["Chronicle"],
    )
    assert payload.new_entries_markdown == ""
