"""Output renderers: coloured terminal report and GitHub-flavoured Markdown."""

from __future__ import annotations

import sys
import textwrap

from .diff import DiffStats
from .schema import Review

ANSI = {
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "green": "\033[92m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}

SEVERITY_COLOR = {"critical": "red", "high": "yellow", "medium": "blue", "low": "cyan"}
TYPE_BADGE = {
    "bug": ("red", "BUG     "),
    "security": ("yellow", "SEC     "),
    "performance": ("blue", "PERF    "),
    "style": ("cyan", "STYLE   "),
}
SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}

# Hidden marker so the GitHub Action can find and update its own comment.
COMMENT_MARKER = "<!-- ai-code-review -->"


def color(name: str, text: str, enabled: bool | None = None) -> str:
    if enabled is None:
        enabled = sys.stdout.isatty()
    return f"{ANSI.get(name, '')}{text}{ANSI['reset']}" if enabled else text


def score_bar(score: int, width: int = 20, use_color: bool | None = None) -> str:
    filled = round(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    col = "green" if score >= 75 else ("yellow" if score >= 45 else "red")
    return color(col, bar, use_color) + color("dim", f" {score}/100", use_color)


def to_terminal(review: Review, stats: DiffStats, model: str, use_color: bool | None = None) -> str:
    def c(name: str, text: str) -> str:
        return color(name, text, use_color)

    W = 64
    counts = review.counts()
    out = [
        "",
        c("bold", "  " + "▄" * W),
        c("bold", f"  {'AI CODE REVIEW ASSISTANT':^{W}}"),
        c("dim", f"  {'Powered by ' + model:^{W}}"),
        c("bold", "  " + "▀" * W),
        "",
        f"  {c('dim', '📄 Files:')} {c('bold', str(stats.files))}   "
        f"{c('dim', '± Lines:')} {c('bold', str(stats.lines_changed))}   "
        f"{c('dim', 'Issues:')} {c('bold', str(len(review.issues)))}",
        "",
        f"  {c('dim', 'Quality')}  {score_bar(review.score, use_color=use_color)}",
        "",
        "  "
        + "   ".join(
            c(col, f"● {counts[key]} {label}")
            for key, col, label in (
                ("bug", "red", "bugs"),
                ("security", "yellow", "security"),
                ("performance", "blue", "perf"),
                ("style", "cyan", "style"),
            )
        ),
        "",
        c("dim", "  " + "─" * W),
        "",
    ]

    if not review.issues:
        out.append(c("green", "  ✓  No issues found — this diff looks clean!"))
    for idx, iss in enumerate(review.issues, 1):
        col, badge = TYPE_BADGE[iss.type.value]
        out.append(
            f"  {c(col, '[' + badge + ']')}  {c('bold', iss.title)}  "
            f"{c(SEVERITY_COLOR[iss.severity.value], iss.severity.value.upper())}"
        )
        if iss.line:
            out.append(f"              {c('dim', '↳ ' + iss.line)}")
        out.append("")
        out.extend("    " + ln for ln in textwrap.wrap(iss.description, 56))
        out.append("")
        if iss.fix:
            out.append(c("dim", "    ┌─ suggested fix " + "─" * 38))
            out.extend(c("green", f"    │ {ln}") for ln in iss.fix.splitlines())
            out.append(c("dim", "    └" + "─" * 55))
        out.append("")
        if idx < len(review.issues):
            out += [c("dim", "  " + "╌" * W), ""]

    out += [c("bold", "  " + "─" * W), "", f"  {c('bold', 'Overall')}  {review.overall}", ""]
    return "\n".join(out)


def to_markdown(review: Review, stats: DiffStats, model: str) -> str:
    """Render a PR comment. Issues are sorted worst-first and collapsed."""
    counts = review.counts()
    worst = review.max_severity()
    verdict = "✅ Looks good" if worst is None or worst.rank < 2 else "⚠️ Needs changes"

    lines = [
        COMMENT_MARKER,
        f"## 🔍 AI Code Review — {verdict}",
        "",
        f"**Score:** `{review.score}/100` · **Files:** {stats.files} · "
        f"**Lines:** +{stats.additions} / -{stats.deletions}",
        "",
        "| 🐞 Bugs | 🔐 Security | ⚡ Performance | 🎨 Style |",
        "|:--:|:--:|:--:|:--:|",
        f"| {counts['bug']} | {counts['security']} | {counts['performance']} | {counts['style']} |",
        "",
    ]
    if review.overall:
        lines += [f"> {review.overall}", ""]

    for iss in sorted(review.issues, key=lambda i: -i.severity.rank):
        emoji = SEVERITY_EMOJI[iss.severity.value]
        loc = f" — `{iss.line}`" if iss.line else ""
        lines += [
            "<details>",
            f"<summary>{emoji} <b>{iss.severity.value.upper()}</b> · "
            f"{iss.type.value} · {_escape(iss.title)}{loc}</summary>",
            "",
            iss.description,
            "",
        ]
        if iss.fix:
            lines += ["**Suggested fix:**", "", "```", iss.fix, "```", ""]
        lines += ["</details>", ""]

    lines.append(f"<sub>Generated by AI Code Review Assistant · model `{model}`</sub>")
    return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")
