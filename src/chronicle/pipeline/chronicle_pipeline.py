import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from chronicle.agents.librarian_decision_logger import (
    DecisionLogPayload,
    LibrarianDecisionLogger,
    RawInput,
)
from chronicle.agents.library_director import LibraryDirector, Plan
from chronicle.io.knowledge_base import (
    insert_at_top,
    next_dec_sequence,
    reverse_decision_entries,
)


@dataclass
class FileResult:
    """The outcome of processing a single raw artifact through the Chronicle pipeline.

    Attributes:
        raw_path: The raw input file that was processed.
        plan:     The execution plan produced by the Library Director, if successful.
        payload:  The decision-log payload produced by the Decision Logger, if applicable.
        skipped:  True if the file was skipped (no applicable plan entry, missing refs, etc.).
        error:    Error message string if a step failed, otherwise ``None``.
    """

    raw_path: Path
    plan: Optional[Plan]
    payload: Optional[DecisionLogPayload]
    skipped: bool
    error: Optional[str]


class ChroniclePipeline:
    """Orchestrates the Chronicle two-step pipeline for a collection of raw artifacts.

    The pipeline maps the Intelligent Agents architecture:
    - ``raw/``      — artifact / input layer
    - ``compiled/`` — shared external memory / knowledge base
    - ``schema/``   — structural guardrails
    - ``agents/``   — agent definitions / system prompts
    - ``out/``      — intermediate artifacts

    Step 1 (Library Director): Analyzes each raw file and produces a JSON execution plan.
    Step 2 (Librarian Decision Logger): If the plan targets ``compiled/decision-log.md``,
    compiles structured decision entries and inserts them into the knowledge base.

    Future specialist agents (Librarian Risk Curator, Librarian Status Keeper, etc.)
    can be registered via :meth:`register_specialist` without modifying core logic.

    Args:
        director:      A :class:`~chronicle.agents.library_director.LibraryDirector` instance.
        decision_logger: A :class:`~chronicle.agents.librarian_decision_logger.LibrarianDecisionLogger` instance.
        compiled_dir:  Path to the ``compiled/`` shared external memory directory.
        schema_dir:    Path to the ``schema/`` structural guardrails directory.
        out_dir:       Path to the ``out/`` intermediate artifacts directory.
    """

    def __init__(
        self,
        director: LibraryDirector,
        decision_logger: LibrarianDecisionLogger,
        compiled_dir: Path,
        schema_dir: Path,
        out_dir: Path,
    ) -> None:
        self.director = director
        self.decision_logger = decision_logger
        self.compiled_dir = Path(compiled_dir)
        self.schema_dir = Path(schema_dir)
        self.out_dir = Path(out_dir)
        # Registry for future specialist agents keyed by compiled file path.
        self._specialists: Dict[str, Any] = {}

    def register_specialist(self, compiled_path: str, agent: Any) -> None:
        """Register a specialist agent for a specific compiled file path.

        This hook enables future agents — such as ``LibrarianRiskCurator`` for
        ``compiled/risks-and-open-questions.md`` — to be wired in without
        modifying core pipeline logic.

        Args:
            compiled_path: The compiled file path this agent handles
                           (e.g. ``"compiled/risks-and-open-questions.md"``).
            agent:         The specialist agent instance.
        """
        self._specialists[compiled_path] = agent

    def _load_decision_log_template(self) -> str:
        """Load the decision-log schema template, falling back to a minimal default."""
        template_path = self.schema_dir / "compiled-templates" / "decision-log.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8", errors="replace")
        print(f"  [warn] Template not found at {template_path}. Using fallback structure.")
        return (
            "## DEC-YYYY-MM-DD-### — <Short Title>\n\n"
            "- **Status:** <Accepted | Rejected | Proposed | Superseded | [unavailable]>\n"
            "- **Decision date:** <YYYY-MM-DD | [unavailable]>\n"
            "- **Owner:** <Name | Team | [unavailable]>\n\n"
            "### Context\n<Why was this decision needed?>\n\n"
            "### Decision\n<What was decided?>\n\n"
            "### Rationale\n- <Reason>\n\n"
            "### Alternatives considered\n- <Alternative> — <why not>\n\n"
            "### Consequences / Impact\n- <Consequence>\n\n"
            "### References\n- `raw/<path-to-source-file>`\n"
        )

    def process_file(self, raw_path: Path) -> FileResult:
        """Run the full Chronicle pipeline for a single raw artifact.

        Args:
            raw_path: Path to the raw input file.

        Returns:
            A :class:`FileResult` describing the outcome.
        """
        raw_path = Path(raw_path)

        try:
            raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return FileResult(
                raw_path=raw_path,
                plan=None,
                payload=None,
                skipped=True,
                error=f"File not found: {raw_path}",
            )

        # ── Step 1: Library Director ─────────────────────────────────
        print(f"  [Step 1] Library Director analyzing: {raw_path.name}")
        try:
            plan = self.director.run(str(raw_path), raw_text)
        except Exception as exc:
            return FileResult(
                raw_path=raw_path,
                plan=None,
                payload=None,
                skipped=True,
                error=f"Library Director failed: {exc}",
            )

        # Persist plan to out/plan.json
        self.out_dir.mkdir(parents=True, exist_ok=True)
        plan_out = self.out_dir / "plan.json"
        plan_data = {
            "affected_files": [
                {
                    "path": f.path,
                    "operation": f.operation,
                    "why": f.why,
                    "raw_refs": f.raw_refs,
                }
                for f in plan.affected_files
            ]
        }
        plan_out.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
        print(f"  [Step 1] Plan saved to: {plan_out}")

        if not plan.targets_decision_log():
            print("  [Skip] Plan does not target decision-log for append.")
            return FileResult(
                raw_path=raw_path, plan=plan, payload=None, skipped=True, error=None
            )

        # ── Step 2: Librarian Decision Logger ────────────────────────
        print("  [Step 2] Librarian Decision Logger compiling entries...")
        compiled_decision_log = self.compiled_dir / "decision-log.md"
        template_text = self._load_decision_log_template()

        entry = plan.decision_log_entry()
        raw_refs = entry.raw_refs if entry else []
        raw_inputs: List[RawInput] = []
        for ref in raw_refs:
            ref_path = Path(ref.split("#")[0])
            try:
                content = ref_path.read_text(encoding="utf-8", errors="replace")
                raw_inputs.append(RawInput(ref=ref, content=content))
            except FileNotFoundError:
                print(f"  [warn] Raw ref not found, skipping: {ref_path}")

        if not raw_inputs:
            return FileResult(
                raw_path=raw_path,
                plan=plan,
                payload=None,
                skipped=True,
                error="None of the raw_refs files could be found.",
            )

        start_seq = next_dec_sequence(str(compiled_decision_log))
        print(f"  [info] Next DEC sequence: {start_seq:03d}")

        try:
            payload = self.decision_logger.run(
                plan=plan,
                raw_inputs=raw_inputs,
                template_text=template_text,
                start_seq=start_seq,
            )
        except Exception as exc:
            return FileResult(
                raw_path=raw_path,
                plan=plan,
                payload=None,
                skipped=False,
                error=f"Librarian Decision Logger failed: {exc}",
            )

        # Persist payload to out/decisionlog_payload.json
        payload_out = self.out_dir / "decisionlog_payload.json"
        payload_data = {
            "append_to": payload.append_to,
            "new_entries_markdown": payload.new_entries_markdown,
        }
        payload_out.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")
        print(f"  [Step 2] Payload saved to: {payload_out}")

        # Insert reversed entries at top of compiled/decision-log.md
        reversed_entries = reverse_decision_entries(payload.new_entries_markdown)
        insert_at_top(str(compiled_decision_log), reversed_entries)
        print(f"  [Step 2] Entries inserted into: {compiled_decision_log}")

        return FileResult(
            raw_path=raw_path, plan=plan, payload=payload, skipped=False, error=None
        )

    def process_directory(self, raw_dir: Path) -> List[FileResult]:
        """Run the Chronicle pipeline for all ``.md`` files in a directory.

        Files are processed in alphabetical order, matching the behaviour of
        the original ``run_project_memory.ps1`` script.  Processing continues
        past individual file failures so a single bad artifact does not halt
        the entire run.

        Args:
            raw_dir: Directory containing raw ``.md`` artifact files.

        Returns:
            A list of :class:`FileResult` objects, one per ``.md`` file found.
        """
        raw_dir = Path(raw_dir)
        md_files = sorted(
            f for f in raw_dir.glob("*.md") if f.name != ".gitkeep"
        )

        if not md_files:
            print(f"[warn] No .md files found in {raw_dir}")
            return []

        results: List[FileResult] = []
        total = len(md_files)
        for idx, raw_path in enumerate(md_files, start=1):
            print(f"\n{'─' * 60}")
            print(f"  [{idx}/{total}] {raw_path.name}")
            print(f"{'─' * 60}")
            result = self.process_file(raw_path)
            results.append(result)
            if result.error:
                print(f"  [error] {result.error}")
            elif result.skipped:
                print(f"  [skip] No applicable entries for this file.")
            else:
                print(f"  [ok] {raw_path.name} processed successfully.")

        return results
