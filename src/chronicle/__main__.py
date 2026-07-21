import argparse
import sys
from pathlib import Path

from chronicle.agents.librarian_decision_logger import LibrarianDecisionLogger
from chronicle.agents.library_director import LibraryDirector
from chronicle.llm.azure_openai_client import AzureOpenAIClient
from chronicle.pipeline.chronicle_pipeline import ChroniclePipeline

_BANNER = """
============================================================
  Chronicle — Continuous Project Knowledge Compilation
  Multi-Agent LLM System for Structured Project Knowledge
============================================================
"""


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chronicle",
        description=(
            "Chronicle: A Multi-Agent LLM System for Continuous Project Knowledge Compilation.\n"
            "Transforms raw project artifacts into structured entries in the compiled/ knowledge base."
        ),
    )
    parser.add_argument(
        "--raw-dir",
        default="raw/meetings/2026",
        metavar="DIR",
        help="Directory containing raw artifact files (default: raw/meetings/2026)",
    )
    parser.add_argument(
        "--compiled-dir",
        default="compiled",
        metavar="DIR",
        help="Shared external memory / knowledge base directory (default: compiled)",
    )
    parser.add_argument(
        "--agents-dir",
        default="agents",
        metavar="DIR",
        help="Agent definition / system-prompt directory (default: agents)",
    )
    parser.add_argument(
        "--schema-dir",
        default="schema",
        metavar="DIR",
        help="Structural guardrails / template directory (default: schema)",
    )
    parser.add_argument(
        "--out-dir",
        default="out",
        metavar="DIR",
        help="Intermediate artifact output directory (default: out)",
    )
    parser.add_argument(
        "--max-tokens-plan",
        type=int,
        default=600,
        metavar="N",
        help="Max completion tokens for the Library Director (default: 600)",
    )
    parser.add_argument(
        "--max-tokens-decision",
        type=int,
        default=800,
        metavar="N",
        help="Max completion tokens for the Librarian Decision Logger (default: 800)",
    )
    return parser


def main() -> int:
    """Run the Chronicle pipeline and return an exit code (0 = success)."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    print(_BANNER)

    # ── LLM client (reads ENDPOINT_URL, DEPLOYMENT_NAME, AZURE_OPENAI_API_KEY) ──
    try:
        llm_client = AzureOpenAIClient.from_env()
    except EnvironmentError as exc:
        print(f"[error] {exc}")
        return 1

    agents_dir = Path(args.agents_dir)

    director = LibraryDirector(
        name="Library Director",
        system_prompt_path=str(agents_dir / "library-director.md"),
        llm_client=llm_client,
    )
    decision_logger = LibrarianDecisionLogger(
        name="Librarian Decision Logger",
        system_prompt_path=str(agents_dir / "librarian-decision-logger.md"),
        llm_client=llm_client,
    )

    pipeline = ChroniclePipeline(
        director=director,
        decision_logger=decision_logger,
        compiled_dir=Path(args.compiled_dir),
        schema_dir=Path(args.schema_dir),
        out_dir=Path(args.out_dir),
    )

    results = pipeline.process_directory(Path(args.raw_dir))

    ok = sum(1 for r in results if not r.skipped and not r.error)
    skipped = sum(1 for r in results if r.skipped)
    errors = sum(1 for r in results if r.error)

    print(f"\n{'=' * 60}")
    print(f"  Chronicle complete — {ok} processed, {skipped} skipped, {errors} error(s)")
    print(f"  Compiled knowledge base: {args.compiled_dir}/decision-log.md")
    print(f"{'=' * 60}\n")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
