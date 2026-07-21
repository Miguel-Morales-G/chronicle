from pathlib import Path


def load_prompt(path: str) -> str:
    """Load a prompt file and return its contents as a string.

    Args:
        path: Path to the prompt markdown file.

    Returns:
        The file contents as a UTF-8 string.

    Raises:
        FileNotFoundError: If the prompt file does not exist at the given path.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {p.resolve()}\n"
            "Ensure the agents/ directory is present and the path is correct."
        )
    return p.read_text(encoding="utf-8", errors="replace")
