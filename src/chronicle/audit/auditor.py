"""Auditor — Chronicle's Evaluation Agent.

The Auditor reads the compiled knowledge base and performs a single LLM call
to detect semantic near-duplicates in the glossary.  All other checks are
deterministic and provided as pre-computed input via :func:`run_all_checks`.

The Auditor has **no write access** to ``compiled/``, ``raw/``, ``schema/``,
or ``agents/``.  It only produces a list of :class:`~chronicle.audit.checks.Finding`
objects that the harness merges with the deterministic findings before
rendering the report.
"""

from typing import List, Optional, Tuple

from chronicle.agents.base_agent import BaseAgent
from chronicle.audit.checks import Finding
from chronicle.io.json_utils import ChronicleJsonError, safe_parse_json


class Auditor(BaseAgent):
    """Evaluation agent — Chronicle Auditor V1.

    Makes **at most one** LLM call per run: a scoped semantic near-duplicate
    check on the glossary.  If the glossary is empty or absent the LLM call
    is skipped entirely and an empty list is returned immediately.

    After each :meth:`run` call the token counts from the LLM response are
    stored in :attr:`_last_llm_tokens` (``None`` when no LLM call was made)
    so the pipeline can surface them in the report metrics.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # (prompt_tokens, completion_tokens) from the most recent run(), or None.
        self._last_llm_tokens: Optional[Tuple[int, int]] = None

    def run(
        self,
        glossary_text: str,
        max_tokens: int = 400,
    ) -> List[Finding]:
        """Run the semantic near-duplicate glossary check via a single LLM call.

        Args:
            glossary_text: Full contents of ``compiled/glossary.md``.
                           Pass an empty string if the file does not exist.
            max_tokens:    Maximum completion tokens (default 400 — small,
                           scoped prompt to minimise cost).

        Returns:
            A list of :class:`~chronicle.audit.checks.Finding` objects with
            ``severity="notice"`` and ``check="glossary-semantic-duplicates"``.
            Returns ``[]`` if no near-duplicates are found or the glossary is empty.

        Raises:
            ChronicleJsonError: If the LLM's response is not valid JSON.
        """
        self._last_llm_tokens = None  # reset on every call

        if not glossary_text.strip():
            return []

        user_prompt = self._build_semantic_check_prompt(glossary_text)
        response = self._call_llm(user_prompt, max_tokens=max_tokens)
        self._last_llm_tokens = (response.prompt_tokens, response.completion_tokens)

        data = safe_parse_json(response.text)  # raises ChronicleJsonError on bad JSON

        raw_findings = data.get("semantic_findings", [])
        findings: List[Finding] = []
        for item in raw_findings:
            findings.append(Finding(
                severity="notice",
                check="glossary-semantic-duplicates",
                location=item.get("location", "compiled/glossary.md"),
                detail=item.get("detail", ""),
                recommendation=item.get("recommendation", ""),
            ))
        return findings

    @staticmethod
    def _build_semantic_check_prompt(glossary_text: str) -> str:
        """Build the user prompt for the semantic near-duplicate check.

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
