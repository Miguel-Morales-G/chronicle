import json
from dataclasses import dataclass
from typing import List

from chronicle.agents.base_agent import BaseAgent
from chronicle.agents.library_director import Plan
from chronicle.io.json_utils import safe_parse_json


@dataclass
class GlossaryPayload:
    """The structured payload produced by the Librarian Glossary Curator.

    Attributes:
        append_to:            Repository-relative path to the compiled glossary file.
        new_entries_markdown: Markdown block containing one or more new glossary entries.
    """

    append_to: str
    new_entries_markdown: str


class LibrarianGlossaryCurator(BaseAgent):
    """Specialist knowledge agent.

    Uses the Library Director's plan plus the raw artifact(s) to produce
    structured glossary entries for ``compiled/glossary.md``.
    Follows the schema defined in ``schema/compiled-templates/glossary.md``.
    Skips terms already present in the compiled glossary.
    """

    def run(
        self,
        plan: Plan,
        raw_inputs: list,
        template_text: str,
        existing_terms: List[str],
        max_tokens: int = 600,
    ) -> GlossaryPayload:
        """Produce a validated glossary payload.

        Args:
            plan:           The execution plan produced by the Library Director.
            raw_inputs:     Raw source files (ref + content) to compile from.
            template_text:  Contents of ``schema/compiled-templates/glossary.md``.
            existing_terms: List of term strings already in ``compiled/glossary.md``.
                            The model will skip these to avoid duplication.
            max_tokens:     Maximum number of completion tokens (default 600).

        Returns:
            A :class:`GlossaryPayload` with ``append_to`` and ``new_entries_markdown``.

        Raises:
            ValueError: If the plan does not target the glossary for additive operation,
                        or if the model response is missing required fields.
            ChronicleJsonError: If the model's response is not valid JSON.
        """
        entry = plan.glossary_entry()
        if entry is None:
            raise ValueError(
                "LibrarianGlossaryCurator requires a plan entry for "
                "compiled/glossary.md with operation=additive."
            )

        raw_refs = entry.raw_refs
        raw_inputs_block = "\n\n---\n\n".join(
            f"### SOURCE: {ri.ref}\n\n{ri.content}" for ri in raw_inputs
        )

        user_prompt = self._build_glossary_prompt(
            template_text=template_text,
            raw_refs=raw_refs,
            raw_inputs_block=raw_inputs_block,
            existing_terms=existing_terms,
        )

        response = self._call_llm(user_prompt, max_tokens=max_tokens)
        data = safe_parse_json(response.text)

        if "new_entries_markdown" not in data:
            raise ValueError(
                "Model response is missing required field 'new_entries_markdown'.\n"
                f"Response keys: {list(data.keys())}"
            )

        return GlossaryPayload(
            append_to=data.get("append_to", "compiled/glossary.md"),
            new_entries_markdown=data["new_entries_markdown"],
        )

    @staticmethod
    def _build_glossary_prompt(
        template_text: str,
        raw_refs: List[str],
        raw_inputs_block: str,
        existing_terms: List[str],
    ) -> str:
        """Build the Compilation Mode user prompt for the glossary.

        Args:
            template_text:    The glossary schema template text.
            raw_refs:         List of raw source reference strings.
            raw_inputs_block: Combined raw source content block.
            existing_terms:   Terms already in the glossary — must be skipped.

        Returns:
            The formatted user prompt string.
        """
        raw_refs_json = json.dumps(raw_refs, indent=2)
        existing_terms_json = json.dumps(existing_terms, indent=2)
        return f"""You are in **Compilation Mode** for **compiled/glossary.md**.

Your task:
- Extract ONLY terms that are explicitly defined or clearly established in the raw input(s) below.
- Produce ONLY new glossary entries following the provided schema template.
- Return a STRICT JSON object only (no Markdown outside JSON, no commentary).

## Constraints (must follow)
- Output MUST be valid JSON and MUST match the exact schema described below.
- Do NOT invent terms or definitions not supported by the raw input.
- Do NOT include any term already present in the EXISTING_TERMS list (case-insensitive match).
- Each entry MUST start with a level-2 heading: `## <Term>`.
- Each entry MUST include a `**Introduced in:**` field citing the raw source path.
- If no new terms are found, return `"new_entries_markdown": ""`.

## Output JSON (STRICT)
Return exactly:

{{
  "append_to": "compiled/glossary.md",
  "new_entries_markdown": "<one or more glossary entries in Markdown, or empty string>"
}}

## Glossary schema template
{template_text}

## EXISTING_TERMS (do NOT produce entries for these — case-insensitive)
{existing_terms_json}

## RAW_REFS (must cite these in each entry)
{raw_refs_json}

## Raw inputs to compile
{raw_inputs_block}
"""
