import json
import pytest
from conftest import FakeLLMClient
from chronicle.agents.librarian_decision_logger import (
    DecisionLogPayload,
    LibrarianDecisionLogger,
    RawInput,
)
from chronicle.agents.library_director import AffectedFile, Plan
from chronicle.io.json_utils import ChronicleJsonError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = json.dumps(
    {
        "append_to": "compiled/decision-log.md",
        "new_entries_markdown": (
            "## DEC-2026-01-08-001 — Use Python\n\n"
            "- **Status:** Accepted\n"
            "- **Decision date:** 2026-01-08\n\n"
            "### References\n"
            "- `raw/meetings/2026/meeting.md`\n"
        ),
    }
)


def _decision_plan():
    return Plan(
        affected_files=[
            AffectedFile(
                path="compiled/decision-log.md",
                operation="append",
                why="Contains a decision.",
                raw_refs=["raw/meetings/2026/meeting.md"],
            )
        ]
    )


def _make_logger(tmp_path, responses):
    prompt_file = tmp_path / "librarian-decision-logger.md"
    prompt_file.write_text("You are the Librarian Decision Logger.", encoding="utf-8")
    client = FakeLLMClient(responses=responses)
    logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(prompt_file),
        llm_client=client,
    )
    return logger, client


_RAW_INPUTS = [RawInput(ref="raw/meetings/2026/meeting.md", content="# Meeting\n\nDecided to use Python.")]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_returns_decision_log_payload(tmp_path):
    logger, _ = _make_logger(tmp_path, [_VALID_PAYLOAD])
    payload = logger.run(
        plan=_decision_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="## DEC-YYYY-MM-DD-### — <Title>",
        start_seq=1,
    )
    assert isinstance(payload, DecisionLogPayload)
    assert payload.append_to == "compiled/decision-log.md"
    assert payload.new_entries_markdown != ""


def test_run_payload_contains_decision_entry(tmp_path):
    logger, _ = _make_logger(tmp_path, [_VALID_PAYLOAD])
    payload = logger.run(
        plan=_decision_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="",
        start_seq=1,
    )
    assert "DEC-2026-01-08-001" in payload.new_entries_markdown


def test_run_raises_when_plan_has_no_decision_entry(tmp_path):
    logger, _ = _make_logger(tmp_path, [_VALID_PAYLOAD])
    empty_plan = Plan(affected_files=[])
    with pytest.raises(ValueError, match="requires a plan entry"):
        logger.run(
            plan=empty_plan,
            raw_inputs=_RAW_INPUTS,
            template_text="",
            start_seq=1,
        )


def test_run_raises_when_response_missing_new_entries_markdown(tmp_path):
    bad_payload = json.dumps({"append_to": "compiled/decision-log.md"})
    logger, _ = _make_logger(tmp_path, [bad_payload])
    with pytest.raises(ValueError, match="new_entries_markdown"):
        logger.run(
            plan=_decision_plan(),
            raw_inputs=_RAW_INPUTS,
            template_text="",
            start_seq=1,
        )


def test_run_raises_on_invalid_json(tmp_path):
    logger, _ = _make_logger(tmp_path, ["not json"])
    with pytest.raises(ChronicleJsonError):
        logger.run(
            plan=_decision_plan(),
            raw_inputs=_RAW_INPUTS,
            template_text="",
            start_seq=1,
        )


def test_prompt_contains_start_seq(tmp_path):
    logger, client = _make_logger(tmp_path, [_VALID_PAYLOAD])
    logger.run(
        plan=_decision_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="template content",
        start_seq=7,
    )
    assert "START_SEQ = 007" in client.calls[0]["user_prompt"]


def test_prompt_contains_raw_refs(tmp_path):
    logger, client = _make_logger(tmp_path, [_VALID_PAYLOAD])
    logger.run(
        plan=_decision_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="template",
        start_seq=1,
    )
    assert "raw/meetings/2026/meeting.md" in client.calls[0]["user_prompt"]


def test_prompt_contains_template_text(tmp_path):
    logger, client = _make_logger(tmp_path, [_VALID_PAYLOAD])
    logger.run(
        plan=_decision_plan(),
        raw_inputs=_RAW_INPUTS,
        template_text="## UNIQUE_TEMPLATE_MARKER",
        start_seq=1,
    )
    assert "## UNIQUE_TEMPLATE_MARKER" in client.calls[0]["user_prompt"]
