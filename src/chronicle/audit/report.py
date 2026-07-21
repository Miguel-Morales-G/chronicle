"""Report generation for Chronicle Auditor V1.

All functions are pure (no side effects) except :func:`write_audit_report`.
Sequence numbering follows the DEC-ID convention used in ``knowledge_base.py``.
"""

import re
from datetime import date
from pathlib import Path
from typing import List, Optional

from chronicle.audit.checks import Finding


# ── Constants ─────────────────────────────────────────────────────────────────

_REPORT_PATTERN = re.compile(
    r"^audit-report-(\d{4}-\d{2}-\d{2})-(\d{3})\.md$", re.IGNORECASE
)

# Number of deterministic checks always executed in V1.
_N_DETERMINISTIC_CHECKS = 5


# ── Sequence numbering ────────────────────────────────────────────────────────


def next_audit_sequence(reports_dir: Path, today: Optional[date] = None) -> int:
    """Return the next available audit-report sequence number for today's date.

    Scans *reports_dir* for files matching
    ``audit-report-YYYY-MM-DD-###.md`` with today's date and returns one
    more than the highest sequence found.  Returns 1 if no matching files
    exist.

    Args:
        reports_dir: Path to the ``reports/`` directory.
        today:       Date to use for matching (defaults to ``date.today()``).

    Returns:
        The next integer sequence number (1-based).
    """
    if today is None:
        today = date.today()
    today_str = today.isoformat()
    reports_dir = Path(reports_dir)
    if not reports_dir.exists():
        return 1
    highest = 0
    for p in reports_dir.iterdir():
        m = _REPORT_PATTERN.match(p.name)
        if m and m.group(1) == today_str:
            seq = int(m.group(2))
            if seq > highest:
                highest = seq
    return highest + 1


# ── Report rendering ──────────────────────────────────────────────────────────


def render_report(
    deterministic: List[Finding],
    semantic: List[Finding],
    metrics: dict,
) -> str:
    """Render the full audit report as a Markdown string.

    Args:
        deterministic: Findings from the five deterministic checks.
        semantic:      Findings from the LLM semantic check.
        metrics:       Dict with the following keys:

                       - ``date``              — ISO date string (``YYYY-MM-DD``)
                       - ``seq``               — integer sequence number for the day
                       - ``dec_entries``       — number of DEC entries in decision-log
                       - ``glossary_terms``    — number of terms in glossary
                       - ``trigger``           — run trigger label (e.g. ``"every-5"``)
                       - ``generated_at``      — ISO-8601 timestamp string
                       - ``prompt_tokens``     — int or ``None``
                       - ``completion_tokens`` — int or ``None``

    Returns:
        Full Markdown string suitable for writing to ``reports/``.
    """
    all_findings = deterministic + semantic
    errors   = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warning"]
    notices  = [f for f in all_findings if f.severity == "notice"]

    if errors:
        overall = "FAIL"
    elif warnings:
        overall = "WARN"
    else:
        overall = "OK"

    report_id = f"{metrics['date']}-{metrics['seq']:03d}"
    lines: List[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        f"# Chronicle Audit Report — {report_id}\n",
        f"- **Date:** {metrics['date']}",
        "- **Compiled dir:** compiled/",
        (
            f"- **Files audited:** decision-log.md "
            f"({metrics['dec_entries']} entries), "
            f"glossary.md ({metrics['glossary_terms']} terms)"
        ),
        f"- **Run trigger:** {metrics.get('trigger', 'manual')}",
        f"- **Overall status:** {overall}\n",
    ]

    # ── Summary ───────────────────────────────────────────────────────────────
    lines += [
        "## Summary\n",
        "| Severity | Count |",
        "|----------|-------|",
        f"| Errors   | {len(errors)}     |",
        f"| Warnings | {len(warnings)}     |",
        f"| Notices  | {len(notices)}     |\n",
    ]

    # ── Findings ──────────────────────────────────────────────────────────────
    lines.append("## Findings\n")
    if not all_findings:
        lines.append(
            "_No issues found. Knowledge base is structurally healthy._\n"
        )
    else:
        for finding in all_findings:
            label = finding.severity.upper()
            lines += [
                f"### [{label}] {_check_to_title(finding.check)}\n",
                f"- **Check:** `{finding.check}`",
                f"- **Location:** {finding.location}",
                f"- **Detail:** {finding.detail}",
                f"- **Recommendation:** {finding.recommendation}\n",
            ]

    # ── Metrics ───────────────────────────────────────────────────────────────
    call_count = metrics.get(
        "llm_call_count",
        1 if metrics.get("prompt_tokens") is not None else 0,
    )
    pt = metrics.get("prompt_tokens")
    ct = metrics.get("completion_tokens")
    if call_count == 0:
        llm_line = "- LLM calls: 0 (semantic check skipped — knowledge base is empty)"
    else:
        llm_line = f"- LLM calls: {call_count} (tokens: prompt={pt}, completion={ct})"
    lines += [
        "## Metrics\n",
        f"- Decision entries: {metrics['dec_entries']}",
        f"- Glossary terms: {metrics['glossary_terms']}",
        f"- Deterministic checks executed: {_N_DETERMINISTIC_CHECKS}",
        llm_line,
        "",
    ]

    # ── Report meta ───────────────────────────────────────────────────────────
    lines += [
        "## Report Meta\n",
        "- Auditor version: v1",
        f"- Generated: {metrics.get('generated_at', metrics['date'])}",
        "",
    ]

    return "\n".join(lines)


def _check_to_title(check_name: str) -> str:
    """Convert a kebab-case check name to a readable title."""
    return check_name.replace("-", " ").title()


# ── File I/O ──────────────────────────────────────────────────────────────────


def write_audit_report(
    reports_dir: Path, report_date: date, seq: int, content: str
) -> Path:
    """Write the rendered report to ``reports/`` and return its path.

    Creates *reports_dir* (and any missing parents) if it does not yet exist.

    Args:
        reports_dir: Target ``reports/`` directory.
        report_date: Date for the report filename.
        seq:         3-digit sequence number for the filename.
        content:     Full Markdown content to write.

    Returns:
        The :class:`~pathlib.Path` of the created report file.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"audit-report-{report_date.isoformat()}-{seq:03d}.md"
    path = reports_dir / filename
    path.write_text(content, encoding="utf-8")
    return path
