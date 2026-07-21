import json
import pytest
from conftest import FakeLLMClient
from chronicle.agents.library_director import LibraryDirector, Plan
from chronicle.io.json_utils import ChronicleJsonError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PLAN = json.dumps(
    {
        "affected_files": [
            {
                "path": "compiled/decision-log.md",
                "operation": "append",
                "why": "Meeting note contains a decision.",
                "raw_refs": ["raw/meetings/2026/meeting.md"],
            }
        ]
    }
)


def _make_director(tmp_path, responses):
    prompt_file = tmp_path / "library-director.md"
    prompt_file.write_text("You are the Library Director.", encoding="utf-8")
    client = FakeLLMClient(responses=responses)
    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(prompt_file),
        llm_client=client,
    )
    return director, client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_returns_plan_instance(tmp_path):
    director, _ = _make_director(tmp_path, [_VALID_PLAN])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting\n\nWe decided to use Python.")
    assert isinstance(plan, Plan)


def test_run_parses_affected_files(tmp_path):
    director, _ = _make_director(tmp_path, [_VALID_PLAN])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert len(plan.affected_files) == 1
    af = plan.affected_files[0]
    assert af.path == "compiled/decision-log.md"
    assert af.operation == "append"
    assert af.raw_refs == ["raw/meetings/2026/meeting.md"]


def test_targets_decision_log_true_for_valid_plan(tmp_path):
    director, _ = _make_director(tmp_path, [_VALID_PLAN])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert plan.targets_decision_log() is True


def test_targets_decision_log_false_for_other_file(tmp_path):
    other_plan = json.dumps(
        {
            "affected_files": [
                {
                    "path": "compiled/current-status.md",
                    "operation": "in_place",
                    "why": "Status update.",
                    "raw_refs": ["raw/meetings/2026/meeting.md"],
                }
            ]
        }
    )
    director, _ = _make_director(tmp_path, [other_plan])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert plan.targets_decision_log() is False


def test_targets_decision_log_false_for_empty_plan(tmp_path):
    empty_plan = json.dumps({"affected_files": []})
    director, _ = _make_director(tmp_path, [empty_plan])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert plan.targets_decision_log() is False


def test_invalid_json_raises_chronicle_json_error(tmp_path):
    director, _ = _make_director(tmp_path, ["not valid json at all"])
    with pytest.raises(ChronicleJsonError):
        director.run("raw/meetings/2026/meeting.md", "# Meeting")


def test_markdown_wrapped_json_is_handled(tmp_path):
    wrapped = "```json\n" + _VALID_PLAN + "\n```"
    director, _ = _make_director(tmp_path, [wrapped])
    plan = director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert plan.targets_decision_log() is True


def test_system_prompt_is_loaded_from_injected_path(tmp_path):
    prompt_file = tmp_path / "custom-director.md"
    prompt_file.write_text("Custom Library Director prompt.", encoding="utf-8")
    client = FakeLLMClient(responses=[_VALID_PLAN])
    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(prompt_file),
        llm_client=client,
    )
    director.run("raw/meetings/2026/meeting.md", "# Meeting")
    assert client.calls[0]["system_prompt"] == "Custom Library Director prompt."


def test_raw_path_appears_in_user_prompt(tmp_path):
    director, client = _make_director(tmp_path, [_VALID_PLAN])
    director.run("raw/meetings/2026/my-special-meeting.md", "# Meeting")
    assert "my-special-meeting.md" in client.calls[0]["user_prompt"]
