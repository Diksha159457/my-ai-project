# 🔍 AI Code Review Assistant

> **Hackathon Project** · Built in 24 hours, hardened afterwards · Powered by Groq + LLaMA 3.3 70B

[![CI](https://github.com/Diksha159457/my-ai-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Diksha159457/my-ai-project/actions/workflows/ci.yml)
[![AI Code Review](https://github.com/Diksha159457/my-ai-project/actions/workflows/ai-review.yml/badge.svg)](https://github.com/Diksha159457/my-ai-project/actions/workflows/ai-review.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)

An AI agent that reviews git diffs and pull requests in real-time — detecting bugs, security vulnerabilities, performance bottlenecks, and code quality issues, then generating actionable fix suggestions instantly.

**Why Groq?** Groq's LPU inference gives near-instant responses — code reviews complete in 1–2 seconds, not 10–15.

---

## 🚨 Problem

Developers spend hours manually reviewing pull requests. Critical bugs, SQL injections, hardcoded secrets, and performance regressions slip through — especially under deadline pressure or in large PRs.

**The cost:**
- Security breaches from undetected vulnerabilities
- Production bugs from missed edge cases
- Slow review cycles blocking team velocity

---

## ✅ Solution

An AI-powered code review agent that:

1. **Analyzes git diffs** — reads exact lines changed, not the whole file
2. **Detects 4 issue categories** — bugs, security, performance, code style
3. **Rates severity** — critical / high / medium / low per issue
4. **Generates fix suggestions** — corrected code, not vague warnings
5. **Scores the PR** — 0–100 quality score with overall assessment
6. **Comments on your PRs** — a GitHub Action posts a single sticky review comment and fails the check on blocking issues

---

## 🎥 Demo

> 3-minute demo video → [[Link to demo video]](https://www.loom.com/share/c8a5ec67e73a4dec8048fca51941badd)

**Sample review output (terminal):**

```
  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  AI CODE REVIEW ASSISTANT
  Powered by Groq  ·  llama-3.3-70b
  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

  📄 Files: 1   ± Lines: 12   Issues: 4

  Quality  █████░░░░░░░░░░░░░░░  12/100

  ● 0 bugs   ● 3 security   ● 0 perf   ● 1 style

  [SEC     ]  SQL Injection via string concatenation  CRITICAL
              ↳ auth/login.js line 6

    User input directly concatenated into SQL query.
    Attacker bypasses auth with: ' OR '1'='1

    ┌─ suggested fix ──────────────────────────────────────────
    │ const user = await db.query(
    │   'SELECT * FROM users WHERE username = ?',
    │   [username]
    │ );
    └───────────────────────────────────────────────────────────
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Model | LLaMA 3.3 70B via Groq API |
| Inference | Groq LPU (1–2s responses) |
| Web UI | Vanilla HTML/CSS/JS — zero dependencies |
| CLI | Python 3.10+, Pydantic v2 |
| API | Flask + Gunicorn |
| Integration | Git CLI, CI/CD via exit codes |

---

## 🚀 Quick Start

### Web UI (zero setup)

Open `app.html` in any browser.

1. Enter your Groq API key (free at [console.groq.com](https://console.groq.com))
2. Paste git diff
3. Click **Review code**

### Python CLI

```bash
pip install -e .             # installs the `ai-review` command
export GROQ_API_KEY=gsk_...

git diff HEAD~1 | ai-review                       # review latest commit
ai-review changes.diff                            # review a diff file
ai-review --git origin/main --lang python         # review against a base
ai-review --git origin/main --format markdown     # PR-comment markdown
ai-review changes.diff --output report.json --fail-on critical
```

`python review.py …` still works as before.

| Exit code | Meaning |
|:--:|---|
| `0` | No issue at or above `--fail-on` (default `high`) |
| `1` | Blocking issues found — fails your pipeline |
| `2` | Usage, configuration or provider error |

### HTTP API

```bash
pip install -e ".[server]"
gunicorn app:app
curl -X POST localhost:8000/review -H 'content-type: application/json' \
     -d '{"diff": "...", "lang": "python"}'
```

Input is validated (400 on bad body, 413 over `MAX_DIFF_BYTES`), provider failures map to 502, and `/health` reports whether an API key is configured.

### Automatic PR reviews (GitHub Actions)

This repo reviews its own pull requests with [`.github/workflows/ai-review.yml`](.github/workflows/ai-review.yml):

1. Add a `GROQ_API_KEY` repository secret.
2. Open a PR. The action reviews `base...HEAD`, posts **one sticky comment** (updated on every push, never duplicated), uploads `report.json` as an artifact, and fails the check on high/critical issues.

Copy the workflow into any repo to get the same behaviour. Without the secret (e.g. PRs from forks) the job skips cleanly instead of failing.

---

## 🏗 Architecture

```
            diff (stdin / file / git)
                     │
             ┌───────▼────────┐
             │  diff.py       │  split per file · drop lockfiles
             │  chunk_diff()  │  pack into ≤24k-char chunks
             └───────┬────────┘
                     │  one LLM call per chunk
             ┌───────▼────────┐
             │  engine.py     │  diff wrapped as untrusted <diff>
             │  review_diff() │  retry w/ self-repair on bad JSON,
             └───────┬────────┘  exponential backoff on API errors
                     │
             ┌───────▼────────┐
             │  schema.py     │  Pydantic: normalise enums, clamp score
             │  Review.merge  │  merge chunks (worst score wins)
             └───────┬────────┘
          ┌──────────┼───────────┐
     terminal     markdown      JSON / HTTP
```

### Design decisions

- **Chunk by file, not by bytes.** Large PRs exceed the context window; splitting on `diff --git` boundaries keeps hunks intact so the model never reviews half a function.
- **Validate, don't trust.** LLMs drift (`"Critical"`, `"score": "85"`, stray code fences). A Pydantic schema normalises the output so downstream code (exit codes, PR comments) is deterministic.
- **Self-repair retries.** On malformed JSON the next attempt tells the model what went wrong, instead of blindly re-sending the same prompt.
- **Prompt-injection hygiene.** The diff is fenced in `<diff>` tags and the system prompt tells the model to ignore instructions inside it, so a PR can't talk its way to a perfect score.
- **Injected LLM client.** The engine takes any `(system, user, model) -> str` callable, so the whole pipeline is tested offline and can be pointed at any provider.

---

## 📁 Project Structure

```
├── ai_reviewer/
│   ├── cli.py        # `ai-review` command, exit-code policy
│   ├── diff.py       # diff stats, per-file split, chunking
│   ├── engine.py     # prompt, LLM call, retries, merge
│   ├── render.py     # terminal + GitHub markdown renderers
│   └── schema.py     # Pydantic Review / Issue models
├── app.py            # Flask HTTP API (Render)
├── app.html          # Web UI, single file, no build step
├── review.py         # legacy entry point → ai_reviewer.cli
├── tests/            # 30 offline tests (fake LLM client)
└── .github/workflows/
    ├── ci.yml        # ruff + pytest on 3.10–3.12
    └── ai-review.yml # reviews every PR, sticky comment
```

---

## 🧪 Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest --cov=ai_reviewer        # 30 tests, ~91% coverage, no network needed
```

---

## 🌟 Features

- **4 issue categories** — Bug, Security, Performance, Style
- **4 severity levels** — Critical, High, Medium, Low
- **Fix suggestions** — concrete corrected code per issue
- **Quality score** — 0–100 PR health score with animated ring
- **Split-pane UI** — diff editor left, live results right
- **Terminal colors** — readable output in any terminal
- **CI/CD ready** — configurable `--fail-on` threshold, sticky PR comments
- **Large-PR safe** — per-file chunking, lockfiles skipped automatically
- **Zero frontend deps** — `app.html` is a single self-contained file
- **JSON export** — `--output report.json` for integrations
- **Multiple input modes** — stdin pipe / file / `--git BASE`

---

## 💡 Real-world Impact

- Catches SQL injection, XSS, hardcoded secrets before merge
- Reduces review time for senior engineers
- Onboards junior developers faster with AI-generated explanations
- Scales to any language — Python, JS, Go, Rust, Java, SQL, PHP

---

## 🔮 Future Roadmap

- [x] GitHub PR comment integration (post reviews directly to PR)
- [ ] Inline review comments on exact diff lines
- [ ] GitLab / Bitbucket webhooks
- [ ] Custom rule sets per team / codebase
- [ ] Historical score tracking across PRs
- [ ] VS Code extension

---

## 👤 Author

Built solo in 24 hours · Hackathon May 2026

---

## 📄 License

MIT
