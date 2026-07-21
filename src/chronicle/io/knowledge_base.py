import re
from pathlib import Path


_DEC_PATTERN = re.compile(r"DEC-(\d{4}-\d{2}-\d{2})-(\d{3})", re.IGNORECASE)


def next_dec_sequence(compiled_path: str) -> int:
    """Return the next available DEC sequence number for a given compiled file.

    Scans the file for existing DEC-YYYY-MM-DD-### identifiers and returns
    one higher than the highest sequence found.  Returns 1 if the file is
    absent, empty, or contains no existing DEC entries.

    Args:
        compiled_path: Path to the compiled decision-log markdown file.

    Returns:
        The next integer sequence number (1-based).
    """
    p = Path(compiled_path)
    if not p.exists() or p.stat().st_size == 0:
        return 1
    text = p.read_text(encoding="utf-8", errors="replace")
    matches = _DEC_PATTERN.findall(text)
    if not matches:
        return 1
    highest = max(int(seq) for _, seq in matches)
    return highest + 1


def insert_at_top(compiled_path: str, new_markdown: str) -> None:
    """Insert new Markdown content immediately after the file's top-level heading.

    If the file has no content yet, the new content is written directly.
    If the file starts with a level-1 heading (``# …``), the new block is
    placed after it (and any immediately following blank lines), separated
    from the remainder by a blank line.

    Args:
        compiled_path: Path to the compiled knowledge-base markdown file.
        new_markdown:  The new Markdown block to insert.
    """
    p = Path(compiled_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    lines = existing.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("# "):
        insert_at = 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
    separator = "\n\n" if existing.strip() else ""
    before = "".join(lines[:insert_at])
    after = "".join(lines[insert_at:])
    updated = before + new_markdown.strip() + separator + after
    p.write_text(updated, encoding="utf-8")


def reverse_decision_entries(md: str) -> str:
    """Reverse the order of decision entries within a Markdown block.

    Splits on level-2 DEC headings (``## DEC-YYYY-MM-DD-###``) and reassembles
    them in reverse order, ensuring a blank line separates each entry.

    Args:
        md: A Markdown string containing one or more DEC entries.

    Returns:
        The same entries in reversed order with consistent blank-line separation,
        or the original string unchanged if no DEC entries are found.
    """
    parts = re.split(r"(##\s+DEC-\d{4}-\d{2}-\d{2}-\d{3}[^\n]*\n)", md)
    if len(parts) < 3:
        return md
    entries = []
    i = 1
    while i < len(parts) - 1:
        entry = parts[i] + parts[i + 1]
        entries.append(entry.rstrip() + "\n\n")
        i += 2
    prefix = parts[0].rstrip() + "\n\n" if parts[0].strip() else ""
    reversed_md = prefix + "".join(reversed(entries)).rstrip() + "\n"
    return reversed_md
