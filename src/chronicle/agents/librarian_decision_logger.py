import json
from dataclasses import dataclass
from typing import List

from chronicle.agents.base_agent import BaseAgent
from chronicle.agents.library_director import Plan
from chronicle.io.json_utils import safe_parse_json


@dataclass
class RawInput:
    """A single raw source file to be compiled.

    Attributes:
        ref:     The reference string as it appears in the plan
                 (e.g. ``raw/meetings/2026/note.md``).
        content: The full text content of the file.
    """

    ref: str
    content: str


@dataclass
class DecisionLogPayload:
    """The structured payload produced by the Librarian Decision Logger.

    Attributes:
        append_to:            Repository-relative path to the compiled decision-log file.
        new_entries_markdown: Markdown block containing one or more new DEC entries.
    """

    append_to: str
    new_entries_markdown: str


class LibrarianDecisionLogger(BaseAgent):
    """Specialist knowledge agent.

    Uses the Library Director's plan plus the raw artifact(s) to produce
    structured decision-log entries for ``compiled/decision-log.md``.
    Follows the schema defined in ``schema/compiled-templates/decision-log.md``.
    """

    def run(
        self,
        plan: Plan,
        raw_inputs: List[RawInput],
        template_text: str,
        start_seq: int,
        max_tokens: int = 800,
    ) -> DecisionLogPayload:
        """Produce a validated decision-log payload.

        Args:
            plan:          The execution plan produced by the Library Director.
            raw_inputs:    Raw source files (ref + content) to compile from.
            template_text: Contents of ``schema/compiled-templates/decision-log.md``.
            start_seq:     The next available DEC sequence number (1-based integer).
            max_tokens:    Maximum number of completion tokens (default 800).

        Returns:
            A :class:`DecisionLogPayload` with ``append_to`` and ``new_entries_markdown``.

        Raises:
            ValueError: If the plan does not target the decision log for append,
                        or if the model response is missing required fields.
            ChronicleJsonError: If the model's response is not valid JSON.
        """
        entry = plan.decision_log_entry()
        if entry is None:
            raise ValueError(
                "LibrarianDecisionLogger requires a plan entry for "
                "compiled/decision-log.md with operation=append."
            )

        raw_refs = entry.raw_refs
        raw_inputs_block = "\n\n---\n\n".join(
            f"### SOURCE: {ri.ref}\n\n{ri.content}" for ri in raw_inputs
        )

        user_prompt = self._build_decisionlog_prompt(
            start_seq=start_seq,
            template_text=template_text,
            raw_refs=raw_refs,
            raw_inputs_block=raw_inputs_block,
        )

        response = self._call_llm(user_prompt, max_tokens=max_tokens)
        data = safe_parse_json(response.text)

        if "new_entries_markdown" not in data:
            raise ValueError(
                "Model response is missing required field 'new_entries_markdown'.\n"
                f"Response keys: {list(data.keys())}"
            )

        return DecisionLogPayload(
            append_to=data.get("append_to", "compiled/decision-log.md"),
            new_entries_markdown=data["new_entries_markdown"],
        )

    @staticmethod
    def _build_decisionlog_prompt(
        start_seq: int,
        template_text: str,
        raw_refs: List[str],
        raw_inputs_block: str,
    ) -> str:
        """Build the Compilation Mode user prompt for the decision log.

        Args:
            start_seq:        Starting DEC sequence number for this batch.
            template_text:    The decision-log schema template text.
            raw_refs:         List of raw source reference strings.
            raw_inputs_block: Combined raw source content block.

        Returns:
            The formatted user prompt string.
        """
        raw_refs_json = json.dumps(raw_refs, indent=2)
        return f"""You are in **Compilation Mode** for **compiled/decision-log.md**.

Your task:
- Extract ONLY decisions from the raw input(s) below.
- Produce ONLY new decision-log entries (append blocks) following the provided schema template.
- Return a STRICT JSON object only (no Markdown outside JSON, no commentary).

## Constraints (must follow)
- Output MUST be valid JSON and MUST match the exact schema described below.
- Do NOT include planning output. Do NOT summarize.
- Do NOT invent missing fields. If unknown, omit the field or use `[unavailable]` exactly as allowed by the template.
- Each decision entry MUST start with a level-2 heading: `## <Decision ID> — <Short Title>`.
- Within each entry, metadata fields SHOULD appear as a bullet list immediately after the heading.
- Use DEC IDs in the form `DEC-YYYY-MM-DD-###`.
- The decision date MUST be the meeting date found in the raw input (or `[unavailable]` if not present).
- References: include a `### References` section in each entry listing the raw source path(s) used.

## Ordering
- Generate entries in the order they appear in the meeting note.
- The orchestrator will insert your `new_entries_markdown` at the TOP of the decision-log file (reverse chronological at file level).
- Do not include any file header or title.

## ID numbering
- Use this as your starting sequence number for the first new decision in this batch:
  START_SEQ = {start_seq:03d}
- For the same date, increment ### by +1 for each additional decision.
- Always format ### as 3 digits (001, 002, 003, ...).

## Output JSON (STRICT)
Return exactly:

{{
  "append_to": "compiled/decision-log.md",
  "new_entries_markdown": "<one or more decision entries in Markdown>"
}}

## Decision-log schema template
{template_text}

## RAW_REFS (must cite these in each entry)
{raw_refs_json}

## Raw inputs to compile
{raw_inputs_block}
"""
