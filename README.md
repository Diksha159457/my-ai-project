# 🔍 AI Code Review Assistant

> **Hackathon Project** · Built in 24 hours · Powered by Groq + LLaMA 3.3 70B

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
6. **Exits with error code** — CI/CD integration: fails the pipeline on critical issues

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
| CLI | Python 3.10+ |
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
# Install
pip install -r requirements.txt

# Set API key
export GROQ_API_KEY=gsk_...

# Review your latest commit
git diff HEAD~1 | python review.py

# Review a specific diff file
python review.py changes.diff

# Review from a git base with language hint
python review.py --git HEAD~2 --lang python

# Save JSON report (for CI/CD pipelines)
python review.py changes.diff --output report.json
```

### CI/CD Integration (GitHub Actions)

```yaml
name: AI Code Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - name: AI Code Review
        run: |
          pip install groq
          git diff origin/main | python review.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

The CLI exits with code `1` if bugs or critical security issues are found — automatically fails your pipeline.

---

## 📁 Project Structure

```
ai-code-reviewer/
├── app.html          # Web UI — single file, no build step
├── review.py         # Python CLI
├── requirements.txt  # Python deps (groq)
└── README.md
```

---

## 🌟 Features

- **4 issue categories** — Bug, Security, Performance, Style
- **4 severity levels** — Critical, High, Medium, Low
- **Fix suggestions** — concrete corrected code per issue
- **Quality score** — 0–100 PR health score with animated ring
- **Split-pane UI** — diff editor left, live results right
- **Terminal colors** — readable output in any terminal
- **CI/CD ready** — non-zero exit on critical issues
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

- [ ] GitHub PR comment integration (post reviews directly to PR)
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
