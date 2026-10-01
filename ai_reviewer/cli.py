"""Command-line interface.

Exit codes:
  0  review passed (no issue at/above --fail-on)
  1  review found blocking issues
  2  usage / configuration / provider error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .diff import diff_stats
from .engine import DEFAULT_MODEL, ReviewError, review_diff
from .render import color, to_markdown, to_terminal
from .schema import Severity

EPILOG = """\
Examples:
  git diff HEAD~1 | ai-review
  ai-review changes.diff
  ai-review --git origin/main --format markdown > comment.md
  ai-review my.diff --output report.json --fail-on critical
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-review",
        description="AI Code Review Assistant — LLM review of git diffs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    p.add_argument("file", nargs="?", help="Diff file path (default: stdin)")
    p.add_argument("--git", metavar="BASE", help="Review the output of `git diff BASE`")
    p.add_argument("--lang", default="auto", help="Language hint (python/js/go/…)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Groq model to use")
    p.add_argument("--format", choices=["terminal", "markdown", "json"], default="terminal")
    p.add_argument("--output", metavar="FILE", help="Also save the JSON report to FILE")
    p.add_argument(
        "--fail-on",
        choices=[s.value for s in Severity] + ["never"],
        default="high",
        help="Exit 1 if any issue is at or above this severity (default: high)",
    )
    p.add_argument("--max-chars", type=int, default=24_000, help="Max diff chars per LLM call")
    return p


def read_diff(args: argparse.Namespace) -> str:
    if args.git:
        try:
            r = subprocess.run(
                ["git", "diff", args.git], capture_output=True, text=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise ReviewError(f"git diff {args.git} failed: {getattr(e, 'stderr', e)}") from e
        return r.stdout
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ReviewError("No input. Provide a file, pipe a diff, or use --git BASE")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    err = sys.stderr

    try:
        diff = read_diff(args)
        if not diff.strip():
            print(color("yellow", "⚠  Empty diff — nothing to review."), file=err)
            return 0
        print(color("dim", f"⟳ Reviewing with {args.model}…"), file=err)
        review = review_diff(diff, language=args.lang, model=args.model, max_chars=args.max_chars)
    except ReviewError as e:
        print(color("red", f"✗ {e}"), file=err)
        return 2

    stats = diff_stats(diff)
    if args.format == "markdown":
        print(to_markdown(review, stats, args.model))
    elif args.format == "json":
        print(review.model_dump_json(indent=2))
    else:
        print(to_terminal(review, stats, args.model))

    if args.output:
        Path(args.output).write_text(json.dumps(review.model_dump(mode="json"), indent=2))
        print(color("dim", f"✓ JSON report → {args.output}"), file=err)

    if args.fail_on == "never":
        return 0
    return 1 if review.should_fail(Severity(args.fail_on)) else 0


if __name__ == "__main__":
    sys.exit(main())
