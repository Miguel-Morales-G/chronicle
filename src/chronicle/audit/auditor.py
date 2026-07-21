"""Auditor — Chronicle's Evaluation Agent.

The Auditor reads the compiled knowledge base and performs up to two LLM calls
per run: one to detect semantic near-duplicates in the glossary, and one to
detect semantic near-duplicate decisions in the decision log.  All other checks
are deterministic and provided as pre-computed input via :func:`run_all_checks`.

The Auditor has **no write access** to ``compiled/``, ``raw/``, ``schema/``,
or ``agents/``.  It only produces a list of :class:`~chronicle.audit.checks.Finding`
objects that the harness merges with the deterministic findings before
rendering the report.
"""

from typing import List, Optional, Tuple

from chronicle.agents.base_agent import BaseAgent
from chronicle.audit.checks import Finding, compress_decisions_for_audit
from chronicle.io.json_utils import ChronicleJsonError, safe_parse_json


class Auditor(BaseAgent):
    """Evaluation agent — Chronicle Auditor V1.1.

    Makes **at most two** LLM calls per run:

    1. A scoped semantic near-duplicate check on the glossary
       (skipped if glossary is empty).
    2. A scoped semantic near-duplicate check on decision-log entries
       (skipped if fewer than two entries exist).

    After each :meth:`run` call the cumulative token counts are stored in
    :attr:`_last_llm_tokens` (``None`` when no LLM call was made) and the
    number of actual calls is stored in :attr:`_last_llm_call_count`.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # (prompt_tokens, completion_tokens) totals from the most recent run(), or None.
        self._last_llm_tokens: Optional[Tuple[int, int]] = None
        # Number of LLM calls made during the most recent run().
        self._last_llm_call_count: int = 0

    def run(
        self,
        glossary_text: str,
        decision_log_text: str = "",
        max_tokens: int = 400,
    ) -> List[Finding]:
        """Run semantic near-duplicate checks on the glossary and decision log.

        Args:
            glossary_text:      Full contents of ``compiled/glossary.md``.
                                Pass an empty string if the file does not exist.
            decision_log_text:  Full contents of ``compiled/decision-log.md``.
                                Pass an empty string (default) if absent or not
                                needed.  The check is skipped when fewer than two
                                entries are present.
            max_tokens:         Maximum completion tokens per call (default 400).

        Returns:
            A list of :class:`~chronicle.audit.checks.Finding` objects with
            ``severity="notice"`` and check names ``"glossary-semantic-duplicates"``
            or ``"decision-semantic-duplicates"``.

        Raises:
            ChronicleJsonError: If any LLM response is not valid JSON.
        """
        self._last_llm_tokens = None
        self._last_llm_call_count = 0
        prompt_total = 0
        completion_total = 0
        findings: List[Finding] = []

        # ── Call 1: glossary near-duplicates ───────────────────────────────
        if glossary_text.strip():
            response = self._call_llm(
                self._build_semantic_check_prompt(glossary_text),
                max_tokens=max_tokens,
            )
            prompt_total += response.prompt_tokens
            completion_total += response.completion_tokens
            self._last_llm_call_count += 1

            data = safe_parse_json(response.text)
            for item in data.get("semantic_findings", []):
                findings.append(Finding(
                    severity="notice",
                    check="glossary-semantic-duplicates",
                    location=item.get("location", "compiled/glossary.md"),
                    detail=item.get("detail", ""),
                    recommendation=item.get("recommendation", ""),
                ))

        # ── Call 2: decision near-duplicates (≥2 entries required) ───────────
        compressed = compress_decisions_for_audit(decision_log_text)
        if compressed and "\n" in compressed:
            response = self._call_llm(
                self._build_decision_check_prompt(compressed),
                max_tokens=max_tokens,
            )
            prompt_total += response.prompt_tokens
            completion_total += response.completion_tokens
            self._last_llm_call_count += 1

            data = safe_parse_json(response.text)
            for item in data.get("semantic_findings", []):
                findings.append(Finding(
                    severity="notice",
                    check="decision-semantic-duplicates",
                    location=item.get(
                        "location", "compiled/decision-log.md"
                    ),
                    detail=item.get("detail", ""),
                    recommendation=item.get("recommendation", ""),
                ))

        if self._last_llm_call_count > 0:
            self._last_llm_tokens = (prompt_total, completion_total)

        return findings

    @staticmethod
    def _build_semantic_check_prompt(glossary_text: str) -> str:
        """Build the user prompt for the glossary semantic near-duplicate check.

        Args:
            glossary_text: Full contents of the compiled glossary.

        Returns:
            The user-turn prompt string to send to the LLM.
        """
        return (
            "You are reviewing a project glossary for semantic near-duplicates.\n\n"
            "A near-duplicate is two or more terms that appear to describe the same "
            "concept under different names — for example, 'Knowledge Base' and "
            "'Shared Memory' in the same project likely refer to the same thing.\n\n"
            "Identify any such pairs or groups in the glossary below.\n\n"
            "Return ONLY a single JSON object with this exact shape "
            "(no Markdown outside the JSON, no commentary, no preamble):\n"
            "{\n"
            '  "semantic_findings": [\n'
            "    {\n"
            '      "location": "compiled/glossary.md — <Term A> / <Term B>",\n'
            '      "detail": "<Explanation of why these appear to be near-duplicates>",\n'
            '      "recommendation": "<Suggested action, e.g. merge or cross-reference>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            'Return `"semantic_findings": []` if no near-duplicates are found.\n\n'
            "Do NOT invent findings. Only flag genuine likely duplicates.\n\n"
            "=== GLOSSARY ===\n\n"
            f"{glossary_text.strip()}"
        )

    @staticmethod
    def _build_decision_check_prompt(compressed_decisions: str) -> str:
        """Build the user prompt for the decision semantic near-duplicate check.

        Args:
            compressed_decisions: One compressed line per DEC entry in the
                format produced by :func:`compress_decisions_for_audit`.

        Returns:
            The user-turn prompt string to send to the LLM.
        """
        return (
            "You are reviewing a project decision log for semantic near-duplicates.\n\n"
            "A near-duplicate decision is two or more entries that record essentially "
            "the same decision under different titles or IDs — for example, two "
            "entries both choosing the same technology stack, or two entries both "
            "deciding to reject the same approach.\n\n"
            "Each line below represents one decision entry in the format:\n"
            "  `DEC-ID` | Title | Decision sentence | Date\n\n"
            "Identify any pairs or groups of entries that appear to be near-duplicates.\n\n"
            "Return ONLY a single JSON object with this exact shape "
            "(no Markdown outside the JSON, no commentary, no preamble):\n"
            "{\n"
            '  "semantic_findings": [\n'
            "    {\n"
            '      "location": "compiled/decision-log.md — <DEC-ID-A> / <DEC-ID-B>",\n'
            '      "detail": "<Explanation of why these appear to be near-duplicate decisions>",\n'
            '      "recommendation": "<Suggested action, e.g. consolidate or cross-reference>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            'Return `"semantic_findings": []` if no near-duplicates are found.\n\n'
            "Do NOT invent findings. Only flag genuine likely duplicates.\n\n"
            "=== DECISION ENTRIES ===\n\n"
            f"{compressed_decisions.strip()}"
        )
