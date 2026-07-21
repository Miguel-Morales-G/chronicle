import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from chronicle.audit.checks import (
    Finding,
    count_dec_entries,
    count_glossary_terms,
    run_all_checks,
)
from chronicle.audit.report import (
    next_audit_sequence,
    render_report,
    write_audit_report,
)
from chronicle.agents.librarian_decision_logger import (
    LibrarianDecisionLogger,
    RawInput,
)
from chronicle.agents.library_director import AffectedFile, LibraryDirector, Plan
from chronicle.io.knowledge_base import (
    append_glossary_entries,
    existing_glossary_terms,
    insert_at_top,
    next_dec_sequence,
    reverse_decision_entries,
)


_DEFAULT_DECISION_LOG_TEMPLATE = (
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

_DEFAULT_GLOSSARY_TEMPLATE = (
    "## <Term>\n\n"
    "- **Category:** <domain | technical | process | [unavailable]>\n"
    "- **Introduced in:** `raw/<path-to-source-file>`\n"
    "- **Aliases:** <alias1, alias2 | omit if none>\n\n"
    "<One or two sentence definition.>\n"
)


@dataclass
class FileResult:
    """The outcome of processing a single raw artifact through the Chronicle pipeline.

    Attributes:
        raw_path: The raw input file that was processed.
        plan:     The execution plan produced by the Library Director, if successful.
        payloads: Dict mapping compiled file paths to their serializable payload data.
                  One entry per specialist that ran successfully.
        skipped:  True if no specialist handled any affected file.
        error:    Error message string if a step failed, otherwise ``None``.
    """

    raw_path: Path
    plan: Optional[Plan]
    payloads: Dict[str, Any]
    skipped: bool
    error: Optional[str]


class ChroniclePipeline:
    """Orchestrates the Chronicle pipeline for a collection of raw artifacts.

    The pipeline maps the Intelligent Agents architecture:
    - ``raw/``      — artifact / input layer
    - ``compiled/`` — shared external memory / knowledge base
    - ``schema/``   — structural guardrails
    - ``agents/``   — agent definitions / system prompts
    - ``out/``      — intermediate artifacts

    Step 1 (Library Director): Analyzes each raw file and produces a JSON execution plan.
    Step 2 (Specialist Dispatch): For each affected file in the plan, the corresponding
    registered specialist handler is invoked to compile entries into the knowledge base.

    Built-in active specialists:
    - ``compiled/decision-log.md``  → Librarian Decision Logger
    - ``compiled/glossary.md``      → Librarian Glossary Curator (when provided)

    Future specialist agents (Librarian Risk Curator, Librarian Status Keeper, etc.)
    can be registered via :meth:`register_specialist` without modifying core logic.

    Args:
        director:         A :class:`~chronicle.agents.library_director.LibraryDirector` instance.
        decision_logger:  A :class:`~chronicle.agents.librarian_decision_logger.LibrarianDecisionLogger` instance.
        compiled_dir:     Path to the ``compiled/`` shared external memory directory.
        schema_dir:       Path to the ``schema/`` structural guardrails directory.
        out_dir:          Path to the ``out/`` intermediate artifacts directory.
        glossary_curator: Optional Librarian Glossary Curator instance.
    """

    def __init__(
        self,
        director: LibraryDirector,
        decision_logger: LibrarianDecisionLogger,
        compiled_dir: Path,
        schema_dir: Path,
        out_dir: Path,
        glossary_curator: Any = None,
        auditor: Any = None,
        audit_every: int = 5,
        audit_now: bool = False,
        reports_dir: Optional[Path] = None,
    ) -> None:
        self.director = director
        self.decision_logger = decision_logger
        self.glossary_curator = glossary_curator
        self.auditor = auditor
        self.audit_every = audit_every
        self.audit_now = audit_now
        self.compiled_dir = Path(compiled_dir)
        self.schema_dir = Path(schema_dir)
        self.out_dir = Path(out_dir)
        self.reports_dir = (
            Path(reports_dir) if reports_dir is not None
            else Path(compiled_dir).parent / "reports"
        )

        # Specialist dispatch registry: compiled file path → handler callable.
        # Handlers have signature: (affected_file: AffectedFile) -> Optional[dict]
        self._specialists: Dict[str, Callable] = {
            "compiled/decision-log.md": self._run_decision_log_specialist,
        }
        if glossary_curator is not None:
            self._specialists["compiled/glossary.md"] = self._run_glossary_specialist

    def register_specialist(self, compiled_path: str, handler: Callable) -> None:
        """Register a specialist handler for a specific compiled file path.

        Enables future agents (e.g. ``LibrarianRiskCurator``) to be wired in
        without modifying core pipeline logic.

        The handler receives a single :class:`~chronicle.agents.library_director.AffectedFile`
        and must return a JSON-serializable dict (the payload) or ``None``.

        Args:
            compiled_path: Compiled file path this handler services
                           (e.g. ``"compiled/risks-and-open-questions.md"``).
            handler:       Callable ``(affected_file: AffectedFile) -> Optional[dict]``.
        """
        self._specialists[compiled_path] = handler

    # ── Shared helpers ───────────────────────────────────────────────────────

    def _load_template(self, filename: str, fallback: str) -> str:
        """Load a schema template, returning a fallback string if not found."""
        template_path = self.schema_dir / "compiled-templates" / filename
        if template_path.exists():
            return template_path.read_text(encoding="utf-8", errors="replace")
        print(f"  [warn] Template not found at {template_path}. Using fallback structure.")
        return fallback

    def _load_raw_inputs(self, affected_file: AffectedFile) -> List[RawInput]:
        """Load raw source files referenced in a plan entry."""
        raw_inputs: List[RawInput] = []
        for ref in affected_file.raw_refs:
            ref_path = Path(ref.split("#")[0])
            try:
                content = ref_path.read_text(encoding="utf-8", errors="replace")
                raw_inputs.append(RawInput(ref=ref, content=content))
            except FileNotFoundError:
                print(f"  [warn] Raw ref not found, skipping: {ref_path}")
        return raw_inputs

    # ── Built-in specialist handlers ─────────────────────────────────────────

    def _run_decision_log_specialist(
        self, affected_file: AffectedFile
    ) -> Optional[Dict[str, Any]]:
        """Handle a plan entry targeting compiled/decision-log.md."""
        compiled_path = self.compiled_dir / "decision-log.md"
        template_text = self._load_template("decision-log.md", _DEFAULT_DECISION_LOG_TEMPLATE)
        raw_inputs = self._load_raw_inputs(affected_file)
        if not raw_inputs:
            print(f"  [warn] No raw inputs found for {affected_file.path}. Skipping.")
            return None

        start_seq = next_dec_sequence(str(compiled_path))
        print(f"  [info] Next DEC sequence: {start_seq:03d}")

        payload = self.decision_logger.run(
            plan=Plan(affected_files=[affected_file]),
            raw_inputs=raw_inputs,
            template_text=template_text,
            start_seq=start_seq,
        )

        payload_data = {
            "append_to": payload.append_to,
            "new_entries_markdown": payload.new_entries_markdown,
        }
        payload_out = self.out_dir / "decisionlog_payload.json"
        payload_out.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")
        print(f"  [info] Payload saved to: {payload_out}")

        reversed_entries = reverse_decision_entries(payload.new_entries_markdown)
        insert_at_top(str(compiled_path), reversed_entries)
        print(f"  [info] Entries inserted into: {compiled_path}")

        return payload_data

    def _run_glossary_specialist(
        self, affected_file: AffectedFile
    ) -> Optional[Dict[str, Any]]:
        """Handle a plan entry targeting compiled/glossary.md."""
        compiled_path = self.compiled_dir / "glossary.md"
        template_text = self._load_template("glossary.md", _DEFAULT_GLOSSARY_TEMPLATE)
        raw_inputs = self._load_raw_inputs(affected_file)
        if not raw_inputs:
            print(f"  [warn] No raw inputs found for {affected_file.path}. Skipping.")
            return None

        terms = existing_glossary_terms(str(compiled_path))
        print(f"  [info] Existing glossary terms: {len(terms)}")

        payload = self.glossary_curator.run(
            plan=Plan(affected_files=[affected_file]),
            raw_inputs=raw_inputs,
            template_text=template_text,
            existing_terms=terms,
        )

        if not payload.new_entries_markdown.strip():
            print("  [info] No new glossary terms identified.")
            return {"append_to": payload.append_to, "new_entries_markdown": ""}

        payload_data = {
            "append_to": payload.append_to,
            "new_entries_markdown": payload.new_entries_markdown,
        }
        payload_out = self.out_dir / "glossary_payload.json"
        payload_out.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")
        print(f"  [info] Payload saved to: {payload_out}")

        append_glossary_entries(str(compiled_path), payload.new_entries_markdown)
        print(f"  [info] Entries appended to: {compiled_path}")

        return payload_data

    # ── Core pipeline methods ────────────────────────────────────────────────

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
                payloads={},
                skipped=True,
                error=f"File not found: {raw_path}",
            )

        # ── Step 1: Library Director ──────────────────────────────────────
        print(f"  [Step 1] Library Director analyzing: {raw_path.name}")
        try:
            plan = self.director.run(str(raw_path), raw_text)
        except Exception as exc:
            return FileResult(
                raw_path=raw_path,
                plan=None,
                payloads={},
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

        if not plan.affected_files:
            print("  [Skip] Plan has no affected files.")
            return FileResult(raw_path=raw_path, plan=plan, payloads={}, skipped=True, error=None)

        # ── Step 2: Specialist dispatch ───────────────────────────────────
        payloads: Dict[str, Any] = {}
        errors: List[str] = []
        any_handled = False

        for affected_file in plan.affected_files:
            handler = self._specialists.get(affected_file.path)
            if handler is None:
                print(
                    f"  [Skip] No active specialist for '{affected_file.path}' — future work."
                )
                continue
            any_handled = True
            print(f"  [Step 2] Running specialist for: {affected_file.path}")
            try:
                payload_data = handler(affected_file)
                if payload_data is not None:
                    payloads[affected_file.path] = payload_data
            except Exception as exc:
                errors.append(f"[{affected_file.path}] {exc}")

        if not any_handled:
            return FileResult(raw_path=raw_path, plan=plan, payloads={}, skipped=True, error=None)

        error = "\n".join(errors) if errors else None
        return FileResult(
            raw_path=raw_path, plan=plan, payloads=payloads, skipped=False, error=error
        )

    def _run_audit(self, trigger: str = "manual") -> Optional[Path]:
        """Run the Auditor and write a timestamped report to ``reports/``.

        Executes all five deterministic checks locally then makes one LLM call
        (via the Auditor agent) for the semantic near-duplicate glossary check.
        Writes the rendered Markdown report and returns its path.

        Args:
            trigger: Human-readable label for the run trigger
                     (e.g. ``"every-5"``, ``"end-of-run"``, ``"manual"``).

        Returns:
            The :class:`~pathlib.Path` of the written report file,
            or ``None`` if no Auditor is configured.
        """
        if self.auditor is None:
            return None

        print(f"\n{'═' * 60}")
        print(f"  [Audit] Chronicle Auditor running ({trigger})...")
        print(f"{'═' * 60}")

        # Read compiled knowledge base (gracefully handle absent files)
        dec_path = self.compiled_dir / "decision-log.md"
        gls_path = self.compiled_dir / "glossary.md"
        dec_text = (
            dec_path.read_text(encoding="utf-8", errors="replace")
            if dec_path.exists() else ""
        )
        gls_text = (
            gls_path.read_text(encoding="utf-8", errors="replace")
            if gls_path.exists() else ""
        )

        # Layer A — deterministic checks (no LLM)
        deterministic: List[Finding] = run_all_checks(dec_text, gls_text)

        # Layer B — LLM semantic check
        semantic: List[Finding] = []
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        try:
            semantic = self.auditor.run(gls_text, decision_log_text=dec_text)
            if self.auditor._last_llm_tokens:
                prompt_tokens, completion_tokens = self.auditor._last_llm_tokens
        except Exception as exc:
            print(f"  [warn] Auditor semantic check failed: {exc}")

        # Build metrics
        today = date.today()
        seq = next_audit_sequence(self.reports_dir, today)
        metrics = {
            "date": today.isoformat(),
            "seq": seq,
            "dec_entries": count_dec_entries(dec_text),
            "glossary_terms": count_glossary_terms(gls_text),
            "trigger": trigger,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "llm_call_count": getattr(self.auditor, "_last_llm_call_count", 0),
        }

        content = render_report(deterministic, semantic, metrics)
        report_path = write_audit_report(self.reports_dir, today, seq, content)

        all_findings = deterministic + semantic
        n_e = sum(1 for f in all_findings if f.severity == "error")
        n_w = sum(1 for f in all_findings if f.severity == "warning")
        n_n = sum(1 for f in all_findings if f.severity == "notice")
        print(f"  [Audit] Report written: {report_path.name}")
        print(f"  [Audit] {n_e} error(s), {n_w} warning(s), {n_n} notice(s)")

        return report_path

    def process_directory(self, raw_dir: Path) -> List[FileResult]:
        """Run the Chronicle pipeline for all ``.md`` files in a directory.

        Files are processed in alphabetical order, matching the behaviour of
        the original ``run_project_memory.ps1`` script.  Processing continues
        past individual file failures so a single bad artifact does not halt
        the entire run.

        The Auditor (if configured) is triggered every ``audit_every`` files
        and always at the end of the run if any files remain unaudited.
        Pass ``audit_now=True`` to force a final audit regardless of count.

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
        processed_since_audit = 0

        for idx, raw_path in enumerate(md_files, start=1):
            print(f"\n{'─' * 60}")
            print(f"  [{idx}/{total}] {raw_path.name}")
            print(f"{'─' * 60}")
            result = self.process_file(raw_path)
            results.append(result)
            processed_since_audit += 1

            if result.error:
                print(f"  [error] {result.error}")
            elif result.skipped:
                print(f"  [skip] No applicable entries for this file.")
            else:
                print(f"  [ok] {raw_path.name} processed successfully.")

            # Periodic audit trigger
            if (
                self.auditor is not None
                and self.audit_every > 0
                and processed_since_audit >= self.audit_every
            ):
                self._run_audit(trigger=f"every-{self.audit_every}")
                processed_since_audit = 0

        # End-of-run audit: run if there are un-audited files OR audit_now is set.
        if self.auditor is not None and (self.audit_now or processed_since_audit > 0):
            self._run_audit(trigger="end-of-run")

        return results

