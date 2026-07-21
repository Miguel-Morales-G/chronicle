from dataclasses import dataclass, field
from typing import List, Optional

from chronicle.agents.base_agent import BaseAgent
from chronicle.io.json_utils import ChronicleJsonError, safe_parse_json


@dataclass
class AffectedFile:
    """A single file entry in a Library Director execution plan.

    Attributes:
        path:      Repository-relative path to the compiled file
                   (e.g. ``compiled/decision-log.md``).
        operation: Modification type — ``append``, ``in_place``, or ``additive``.
        why:       One-sentence justification produced by the director.
        raw_refs:  Raw source references that support this plan entry.
    """

    path: str
    operation: str
    why: str = ""
    raw_refs: List[str] = field(default_factory=list)


@dataclass
class Plan:
    """The structured execution plan produced by the Library Director.

    Attributes:
        affected_files: Ordered list of compiled files the director identified as affected.
    """

    affected_files: List[AffectedFile]

    def targets_decision_log(self) -> bool:
        """Return True if the plan includes an append operation to the decision log."""
        return any(
            f.path == "compiled/decision-log.md" and f.operation == "append"
            for f in self.affected_files
        )

    def decision_log_entry(self) -> Optional[AffectedFile]:
        """Return the decision-log ``AffectedFile`` entry, or ``None`` if absent."""
        for f in self.affected_files:
            if f.path == "compiled/decision-log.md" and f.operation == "append":
                return f
        return None

    def glossary_entry(self) -> Optional[AffectedFile]:
        """Return the glossary ``AffectedFile`` entry, or ``None`` if absent."""
        for f in self.affected_files:
            if f.path == "compiled/glossary.md" and f.operation == "additive":
                return f
        return None


class LibraryDirector(BaseAgent):
    """Orchestrator agent.

    Analyzes a single raw artifact and produces a structured JSON execution
    plan that identifies which specialist librarian agents should be invoked
    and which compiled knowledge-base files are affected.

    The Library Director does **not** write to ``compiled/`` directly.
    """

    def run(
        self,
        raw_path: str,
        raw_text: str,
        max_tokens: int = 600,
    ) -> Plan:
        """Analyze a raw artifact and return an execution plan.

        Args:
            raw_path:   Repository-relative path to the raw input file.
                        Used by the model for traceability in ``raw_refs``.
            raw_text:   Contents of the raw input file.
            max_tokens: Maximum number of completion tokens (default 600).

        Returns:
            A :class:`Plan` describing which compiled files are affected.

        Raises:
            ChronicleJsonError: If the model's response is not valid JSON.
        """
        user_prompt = self._build_planning_prompt(raw_path, raw_text)
        response = self._call_llm(user_prompt, max_tokens=max_tokens)
        data = safe_parse_json(response.text)
        affected_files = [
            AffectedFile(
                path=entry.get("path", ""),
                operation=entry.get("operation", ""),
                why=entry.get("why", ""),
                raw_refs=entry.get("raw_refs", []),
            )
            for entry in data.get("affected_files", [])
        ]
        return Plan(affected_files=affected_files)

    @staticmethod
    def _build_planning_prompt(raw_path: str, raw_text: str) -> str:
        """Build the Planning Mode user prompt sent to the model.

        Args:
            raw_path: Repository-relative path to the raw input file.
            raw_text: Contents of the raw input file.

        Returns:
            The formatted user prompt string.
        """
        return f"""You are in **Planning Mode**.

Your task is to analyze the provided raw input(s) and determine which canonical compiled files are affected.

### Instructions
- Do NOT generate or update any compiled content.
- Do NOT summarize the meeting.
- Do NOT invent missing information.
- Base your plan strictly on the information present in the raw input(s).
- Assume no other context exists beyond what is provided.

### Output format (STRICT)
Return a single JSON object with the following shape and nothing else:

```json
{{
  "affected_files": [
    {{
      "path": "compiled/<file>.md",
      "operation": "append|in_place|additive",
      "why": "short justification",
      "raw_refs": ["raw/<path>#<optional_anchor>"]
    }}
  ]
}}
```

### Planning rules
- Include **only** files that are reasonably impacted by the raw input.
- If the raw input contains only decisions, the plan should normally include:
  - `compiled/decision-log.md` with `"operation": "append"`
- Do not include files unless there is clear justification from the raw input.
- Keep `why` to one concise sentence.

### Raw input to analyze
SOURCE_PATH: {raw_path}

```md
{raw_text}
```
"""
