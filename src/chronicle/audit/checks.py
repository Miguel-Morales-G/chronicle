"""Deterministic structural checks for the Chronicle knowledge base.

All check functions accept plain text strings — no file I/O — so they are
fast, reproducible, and easily unit-testable.  Each function returns a
(possibly empty) list of :class:`Finding` objects.

The public entry point :func:`run_all_checks` runs every V1 check in one call.
"""

import re
from dataclasses import dataclass
from typing import List


# ── Compiled regex patterns ───────────────────────────────────────────────────

# Level-2 heading whose content is a valid DEC-YYYY-MM-DD-### identifier.
_DEC_HEADING = re.compile(
    r"^##\s+(DEC-\d{4}-\d{2}-\d{2}-\d{3})", re.MULTILINE
)

# Any word-boundary token that starts with "DEC-" (candidate for validation).
_DEC_CANDIDATE = re.compile(r"\bDEC-[\w-]+", re.IGNORECASE)

# Strict valid DEC ID (full-string match).
_DEC_VALID = re.compile(r"^DEC-\d{4}-\d{2}-\d{2}-\d{3}$")

# Split a document into blocks at every level-2 heading.
_H2_SPLIT = re.compile(r"\n(?=## )")

# Presence of a ### References section inside a decision entry.
_REFERENCES_SECTION = re.compile(r"###\s+References", re.IGNORECASE)

# Presence of a **Introduced in:** metadata bullet.
_INTRODUCED_IN = re.compile(r"\*\*Introduced in:", re.IGNORECASE)

# Level-2 heading term (used for glossary).
_TERM_HEADING = re.compile(r"^##\s+(.+)$", re.MULTILINE)


# ── Finding dataclass ─────────────────────────────────────────────────────────


@dataclass
class Finding:
    """A single audit finding.

    Attributes:
        severity:       One of ``"error"``, ``"warning"``, or ``"notice"``.
        check:          Machine-readable check name (kebab-case).
        location:       Human-readable location string (file + context).
        detail:         Full description of the issue.
        recommendation: Suggested remediation action.
    """

    severity: str
    check: str
    location: str
    detail: str
    recommendation: str


# ── Check 1 — Duplicate DEC IDs ──────────────────────────────────────────────


def find_duplicate_dec_ids(
    text: str, source: str = "compiled/decision-log.md"
) -> List[Finding]:
    """Check for duplicate ``DEC-YYYY-MM-DD-###`` identifiers.

    Scans the text for level-2 headings whose content is a DEC ID and
    reports any ID that appears more than once.

    Args:
        text:   Full text of the decision-log file.
        source: Human-readable location prefix for findings.

    Returns:
        One :class:`Finding` (severity ``"error"``) per duplicated DEC ID.
    """
    matches = _DEC_HEADING.findall(text)
    seen: dict = {}
    for dec_id in matches:
        seen[dec_id] = seen.get(dec_id, 0) + 1

    findings: List[Finding] = []
    for dec_id, count in seen.items():
        if count > 1:
            findings.append(Finding(
                severity="error",
                check="duplicate-dec-id",
                location=f"{source} — {dec_id}",
                detail=f"`{dec_id}` appears {count} times in the decision log.",
                recommendation=(
                    f"Renumber the later occurrence(s) of `{dec_id}` to the next "
                    "available sequence number."
                ),
            ))
    return findings


# ── Check 2 — Malformed DEC IDs ──────────────────────────────────────────────


def find_malformed_dec_ids(
    text: str, source: str = "compiled/decision-log.md"
) -> List[Finding]:
    """Check for DEC-like tokens that do not match the ``DEC-YYYY-MM-DD-###`` format.

    Scans the full text for any token beginning with ``DEC-`` and validates
    its format.  Valid IDs are silently passed; malformed tokens are reported.

    Args:
        text:   Full text of the decision-log file.
        source: Human-readable location prefix for findings.

    Returns:
        One :class:`Finding` (severity ``"error"``) per distinct malformed token.
    """
    candidates = _DEC_CANDIDATE.findall(text)
    findings: List[Finding] = []
    seen_bad: set = set()
    for token in candidates:
        if not _DEC_VALID.match(token) and token not in seen_bad:
            seen_bad.add(token)
            findings.append(Finding(
                severity="error",
                check="malformed-dec-id",
                location=f"{source} — {token}",
                detail=(
                    f"`{token}` does not match the required "
                    "`DEC-YYYY-MM-DD-###` format."
                ),
                recommendation=(
                    "Correct the identifier to use a 4-digit ISO year, 2-digit "
                    "month, 2-digit day, and 3-digit zero-padded sequence "
                    "(e.g. `DEC-2026-07-21-001`)."
                ),
            ))
    return findings


# ── Check 3 — Decisions missing ### References ────────────────────────────────


def find_decisions_missing_references(
    text: str, source: str = "compiled/decision-log.md"
) -> List[Finding]:
    """Check that every ``## DEC-...`` entry contains a ``### References`` section.

    Splits the document into entries at ``## `` boundaries and inspects each
    block that starts with a DEC heading.

    Args:
        text:   Full text of the decision-log file.
        source: Human-readable location prefix for findings.

    Returns:
        One :class:`Finding` (severity ``"warning"``) per entry missing References.
    """
    entries = _H2_SPLIT.split(text.strip())
    findings: List[Finding] = []
    for entry in entries:
        entry = entry.strip()
        if not entry.startswith("## DEC-"):
            continue
        first_line = entry.splitlines()[0] if entry else ""
        if not _REFERENCES_SECTION.search(entry):
            findings.append(Finding(
                severity="warning",
                check="decision-missing-references",
                location=f"{source} — {first_line}",
                detail="This decision entry has no `### References` section.",
                recommendation=(
                    "Add a `### References` section citing the raw source path(s), "
                    "e.g. `- \\`raw/meetings/2026/meeting-note.md\\``."
                ),
            ))
    return findings


# ── Check 4 — Glossary entries missing Introduced-in ─────────────────────────


def find_glossary_missing_introduced_in(
    text: str, source: str = "compiled/glossary.md"
) -> List[Finding]:
    """Check that every glossary entry contains an ``**Introduced in:**`` bullet.

    Splits the document at ``## `` boundaries and checks each entry for the
    required traceability metadata field.

    Args:
        text:   Full text of the glossary file.
        source: Human-readable location prefix for findings.

    Returns:
        One :class:`Finding` (severity ``"warning"``) per entry missing the field.
    """
    entries = _H2_SPLIT.split(text.strip())
    findings: List[Finding] = []
    for entry in entries:
        entry = entry.strip()
        if not entry.startswith("## "):
            continue
        first_line = entry.splitlines()[0]
        term = first_line.lstrip("#").strip()
        if not _INTRODUCED_IN.search(entry):
            findings.append(Finding(
                severity="warning",
                check="glossary-missing-introduced-in",
                location=f"{source} — {term}",
                detail=(
                    f"The glossary entry for `{term}` is missing the required "
                    "`**Introduced in:**` traceability bullet."
                ),
                recommendation=(
                    "Add `- **Introduced in:** \\`raw/<path-to-source-file>\\`` "
                    "to the metadata bullet list for this term."
                ),
            ))
    return findings


# ── Check 5 — Duplicate glossary headings ─────────────────────────────────────


def find_duplicate_glossary_headings(
    text: str, source: str = "compiled/glossary.md"
) -> List[Finding]:
    """Check for duplicate term headings in the glossary (case-insensitive).

    Args:
        text:   Full text of the glossary file.
        source: Human-readable location prefix for findings.

    Returns:
        One :class:`Finding` (severity ``"error"``) per duplicated term.
    """
    headings = [m.group(1).strip() for m in _TERM_HEADING.finditer(text)]
    seen: dict = {}
    for term in headings:
        key = term.lower()
        seen.setdefault(key, []).append(term)

    findings: List[Finding] = []
    for terms in seen.values():
        if len(terms) > 1:
            labels = ", ".join(f"`{t}`" for t in terms)
            findings.append(Finding(
                severity="error",
                check="duplicate-glossary-heading",
                location=f"{source} — {terms[0]}",
                detail=f"The glossary has {len(terms)} entries for the same term: {labels}.",
                recommendation=(
                    "Remove or merge the duplicate entries, keeping the most "
                    "complete definition."
                ),
            ))
    return findings


# ── Counting helpers (used by pipeline metrics) ───────────────────────────────


def count_dec_entries(text: str) -> int:
    """Count valid DEC-ID level-2 headings in *text*."""
    return len(_DEC_HEADING.findall(text))


def count_glossary_terms(text: str) -> int:
    """Count level-2 headings in *text* (glossary term count)."""
    return len(_TERM_HEADING.findall(text))


# ── Public entry point ────────────────────────────────────────────────────────


ALL_DECISION_LOG_CHECKS = [
    find_duplicate_dec_ids,
    find_malformed_dec_ids,
    find_decisions_missing_references,
]

ALL_GLOSSARY_CHECKS = [
    find_glossary_missing_introduced_in,
    find_duplicate_glossary_headings,
]


def run_all_checks(
    decision_log_text: str,
    glossary_text: str,
) -> List[Finding]:
    """Run all V1 deterministic checks and return the combined findings list.

    Args:
        decision_log_text: Full text of ``compiled/decision-log.md``
                           (pass empty string if the file does not exist).
        glossary_text:     Full text of ``compiled/glossary.md``
                           (pass empty string if the file does not exist).

    Returns:
        Combined list of :class:`Finding` objects from all checks.
    """
    findings: List[Finding] = []
    for check_fn in ALL_DECISION_LOG_CHECKS:
        findings.extend(check_fn(decision_log_text))
    for check_fn in ALL_GLOSSARY_CHECKS:
        findings.extend(check_fn(glossary_text))
    return findings
