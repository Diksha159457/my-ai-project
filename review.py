#!/usr/bin/env python3
"""
AI Code Review Assistant
Hackathon Project — AI-powered PR diff reviewer using Groq API (llama-3.3-70b)
Usage:
  git diff HEAD~1 | python review.py
  python review.py changes.diff
  python review.py --git HEAD~2 --lang python --output report.json
"""

import sys
import json
import os
import argparse
import subprocess
from typing import Optional
from groq import Groq

# ─── Prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior software engineer conducting a thorough code review.
Analyze the provided git diff and return a JSON report of all issues found.

Return ONLY valid JSON — no markdown fences, no preamble, no explanation:
{
  "issues": [
    {
      "type": "bug|security|performance|style",
      "severity": "critical|high|medium|low",
      "title": "short descriptive title",
      "line": "filename and/or line reference",
      "description": "what the problem is and why it matters",
      "fix": "corrected code snippet or concrete action"
    }
  ],
  "score": <integer 0-100>,
  "overall": "one sentence summary of the PR quality"
}

Check for: SQL injection, XSS, hardcoded secrets/keys, weak/broken crypto (MD5, SHA1),
missing input validation, missing error handling, N+1 queries, memory leaks,
race conditions, insecure deserialization, auth bypass, path traversal,
command injection, SSRF, sensitive data in logs, dead code, naming issues.

Score: 100 = perfect, 0 = critically broken. Be specific, actionable, and honest."""

# ─── Terminal colors ──────────────────────────────────────────────────────────

ANSI = {
    "red":     "\033[91m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "green":   "\033[92m",
    "cyan":    "\033[96m",
    "magenta": "\033[95m",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "reset":   "\033[0m",
}

def c(color: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{ANSI.get(color,'')}{text}{ANSI['reset']}"

SEVERITY_COLOR = {
    "critical": "red",
    "high":     "yellow",
    "medium":   "blue",
    "low":      "cyan",
}

TYPE_BADGE = {
    "bug":         ("red",     "BUG     "),
    "security":    ("yellow",  "SEC     "),
    "performance": ("blue",    "PERF    "),
    "style":       ("cyan",    "STYLE   "),
}

# ─── Input helpers ────────────────────────────────────────────────────────────

def read_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def read_stdin() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""

def run_git_diff(base: str) -> str:
    try:
        r = subprocess.run(["git", "diff", base], capture_output=True, text=True, check=True)
        return r.stdout
    except subprocess.CalledProcessError as e:
        die(f"git diff {base} failed — are you in a git repo?\n  {e.stderr.strip()}")

def die(msg: str):
    print(c("red", f"\n  ✗ {msg}"))
    sys.exit(1)

# ─── Groq API call ────────────────────────────────────────────────────────────

def review_code(diff: str, language: str = "auto") -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        die("GROQ_API_KEY not set.\n  Get a free key at: https://console.groq.com")

    client = Groq(api_key=api_key)

    lang_hint = f"Programming language: {language}.\n\n" if language != "auto" else ""
    user_msg = f"{lang_hint}{diff}"

    sys.stdout.write(c("dim", "  ⟳ Sending to Groq (llama-3.3-70b)...\r"))
    sys.stdout.flush()

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2000,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ]
    )

    sys.stdout.write("                                          \r")
    raw = chat.choices[0].message.content
    return json.loads(raw)

# ─── Score display ────────────────────────────────────────────────────────────

def score_bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    col = "green" if score >= 75 else ("yellow" if score >= 45 else "red")
    return c(col, bar) + c("dim", f" {score}/100")

# ─── Report printer ───────────────────────────────────────────────────────────

def print_report(result: dict, diff: str):
    issues  = result.get("issues", [])
    score   = result.get("score", 0)
    overall = result.get("overall", "")

    lines_changed = sum(
        1 for l in diff.splitlines()
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
    )
    files_changed = diff.count("diff --git")

    counts = {"bug": 0, "security": 0, "performance": 0, "style": 0}
    for iss in issues:
        t = iss.get("type", "style")
        if t in counts:
            counts[t] += 1

    W = 64
    print()
    print(c("bold", "  " + "▄" * W))
    print(c("bold", f"  {'AI CODE REVIEW ASSISTANT':^{W}}"))
    print(c("dim",  f"  {'Powered by Groq  ·  llama-3.3-70b':^{W}}"))
    print(c("bold", "  " + "▀" * W))
    print()

    # Diff stats
    print(f"  {c('dim','📄 Files:')} {c('bold', str(files_changed))}   "
          f"{c('dim','± Lines:')} {c('bold', str(lines_changed))}   "
          f"{c('dim','Issues:')} {c('bold', str(len(issues)))}")
    print()

    # Score bar
    print(f"  {c('dim','Quality')}  {score_bar(score if isinstance(score,int) else 0)}")
    print()

    # Counts row
    print(
        f"  {c('red',    '● ' + str(counts['bug'])        + ' bug' + ('s' if counts['bug']!=1 else ''))}   "
        f"{c('yellow', '● ' + str(counts['security'])    + ' security')}   "
        f"{c('blue',   '● ' + str(counts['performance']) + ' perf')}   "
        f"{c('cyan',   '● ' + str(counts['style'])       + ' style')}"
    )
    print()
    print(c("dim", "  " + "─" * W))
    print()

    if not issues:
        print(c("green", "  ✓  No issues found — this diff looks clean!"))
    else:
        for idx, iss in enumerate(issues, 1):
            itype    = iss.get("type", "style")
            severity = iss.get("severity", "medium")
            title    = iss.get("title", "Untitled issue")
            line_ref = iss.get("line", "")
            desc     = iss.get("description", "")
            fix      = iss.get("fix", "")

            col, badge_text = TYPE_BADGE.get(itype, ("cyan", "NOTE    "))
            sev_col = SEVERITY_COLOR.get(severity, "cyan")

            # Issue header
            print(f"  {c(col, '[' + badge_text + ']')}  "
                  f"{c('bold', title)}  "
                  f"{c(sev_col, severity.upper())}")
            if line_ref:
                print(f"              {c('dim', '↳ ' + line_ref)}")
            print()

            # Description (wrapped ~56 chars)
            words, line_buf = desc.split(), ""
            for w in words:
                if len(line_buf) + len(w) + 1 > 56:
                    print(f"    {line_buf}")
                    line_buf = w
                else:
                    line_buf = (line_buf + " " + w).strip()
            if line_buf:
                print(f"    {line_buf}")
            print()

            # Fix block
            if fix:
                print(c("dim", "    ┌─ suggested fix " + "─" * 38))
                for ln in fix.splitlines():
                    print(c("green", f"    │ {ln}"))
                print(c("dim", "    └" + "─" * 55))

            print()
            if idx < len(issues):
                print(c("dim", "  " + "╌" * W))
                print()

    print(c("bold", "  " + "─" * W))
    print()
    print(f"  {c('bold','Overall')}  {overall}")
    print()

# ─── JSON export ──────────────────────────────────────────────────────────────

def export_json(result: dict, path: str):
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    print(c("dim", f"  ✓ JSON report → {path}"))

# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="AI Code Review Assistant — powered by Groq",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  git diff HEAD~1 | python review.py
  python review.py changes.diff
  python review.py --git HEAD~2 --lang python
  python review.py my.diff --output report.json
        """
    )
    parser.add_argument("file",     nargs="?",       help="Diff file path")
    parser.add_argument("--git",    metavar="BASE",   help="Run: git diff BASE")
    parser.add_argument("--lang",   default="auto",   help="Language hint (python/js/go/…)")
    parser.add_argument("--output", metavar="FILE",   help="Save JSON report to FILE")
    parser.add_argument("--model",  default="llama-3.3-70b-versatile",
                                                      help="Groq model to use")
    args = parser.parse_args()

    print()
    print(c("bold", "  AI Code Review Assistant"), c("dim", "v2.0 · Groq"))
    print(c("dim",  "  ────────────────────────────────────────"))

    # Collect diff
    if args.git:
        print(c("dim", f"  Running: git diff {args.git}"))
        diff = run_git_diff(args.git)
    elif args.file:
        print(c("dim", f"  Reading: {args.file}"))
        diff = read_file(args.file)
    else:
        diff = read_stdin()
        if not diff:
            die("No input. Provide a file, pipe a diff, or use --git HEAD~1")

    if not diff.strip():
        print(c("yellow", "  ⚠  Empty diff — nothing to review."))
        sys.exit(0)

    preview = diff[:72].replace("\n", " ")
    print(c("dim", f"  Preview: {preview}…"))
    print()

    # Review
    try:
        result = review_code(diff, args.lang)
    except json.JSONDecodeError:
        die("Groq returned unexpected format. Try again.")
    except Exception as e:
        die(str(e))

    # Output
    print_report(result, diff)

    if args.output:
        export_json(result, args.output)

    # Non-zero exit if critical/security issues found
    critical = sum(
        1 for i in result.get("issues", [])
        if i.get("type") in ("bug", "security") or i.get("severity") in ("critical", "high")
    )
    sys.exit(1 if critical else 0)

if __name__ == "__main__":
    main()
