import pytest
from chronicle.io.prompt_loader import load_prompt


def test_load_prompt_returns_file_content(tmp_path):
    prompt_file = tmp_path / "test_prompt.md"
    prompt_file.write_text("You are a test agent.", encoding="utf-8")
    assert load_prompt(str(prompt_file)) == "You are a test agent."


def test_load_prompt_preserves_multiline_content(tmp_path):
    content = "# System Prompt\n\n## Role\nYou are helpful.\n"
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text(content, encoding="utf-8")
    assert load_prompt(str(prompt_file)) == content


def test_load_prompt_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_prompt(str(missing))
    assert str(missing) in str(exc_info.value)


def test_load_prompt_missing_file_message_contains_path(tmp_path):
    missing = tmp_path / "subdir" / "prompt.md"
    with pytest.raises(FileNotFoundError, match="subdir"):
        load_prompt(str(missing))
