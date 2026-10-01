import json

import pytest

from ai_reviewer import Review, ReviewError, chunk_diff, diff_stats, review_diff
from ai_reviewer.cli import main
from ai_reviewer.engine import parse_review
from ai_reviewer.render import COMMENT_MARKER, to_markdown, to_terminal
from ai_reviewer.schema import Severity
from app import create_app

SAMPLE_DIFF = """\
diff --git a/auth/login.py b/auth/login.py
index 1111111..2222222 100644
--- a/auth/login.py
+++ b/auth/login.py
@@ -1,3 +1,4 @@
 def login(db, username):
-    return db.get(username)
+    q = "SELECT * FROM users WHERE name = '" + username + "'"
+    return db.execute(q)
diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-{"a": 1}
+{"a": 2}
"""

GOOD_JSON = json.dumps(
    {
        "issues": [
            {
                "type": "SECURITY",
                "severity": "Critical",
                "title": "SQL injection",
                "line": "auth/login.py:3",
                "description": "User input concatenated into SQL.",
                "fix": "db.execute('SELECT * FROM users WHERE name = ?', [username])",
            }
        ],
        "score": "12",
        "overall": "Unsafe query construction.",
    }
)


class FakeClient:
    """Scripted LLM: returns (or raises) each queued response in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, *, system, user, model):
        self.calls.append({"system": system, "user": user, "model": model})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


# ── diff helpers ────────────────────────────────────────────────────────────


def test_diff_stats_counts_files_and_lines():
    s = diff_stats(SAMPLE_DIFF)
    assert (s.files, s.additions, s.deletions) == (2, 3, 2)


def test_chunk_diff_skips_lockfiles():
    chunks = chunk_diff(SAMPLE_DIFF)
    assert len(chunks) == 1
    assert "package-lock.json" not in chunks[0]
    assert "auth/login.py" in chunks[0]


def test_chunk_diff_respects_budget_and_keeps_all_content():
    files = "".join(f"diff --git a/f{i}.py b/f{i}.py\n+{'x' * 300}\n" for i in range(10))
    chunks = chunk_diff(files, max_chars=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks) == files


def test_chunk_diff_hard_splits_oversized_file():
    big = "diff --git a/big.py b/big.py\n" + "".join(f"+line {i}\n" for i in range(500))
    chunks = chunk_diff(big, max_chars=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks) == big


# ── schema normalisation ────────────────────────────────────────────────────


def test_parse_review_normalises_llm_drift():
    r = parse_review(GOOD_JSON)
    assert r.score == 12
    assert r.issues[0].type.value == "security"
    assert r.issues[0].severity is Severity.CRITICAL


def test_parse_review_accepts_code_fences():
    r = parse_review(f"```json\n{GOOD_JSON}\n```")
    assert r.issues[0].title == "SQL injection"


@pytest.mark.parametrize("score,expected", [(150, 100), (-5, 0), ("n/a", 0), (72.6, 73)])
def test_score_is_clamped(score, expected):
    assert Review.model_validate({"score": score}).score == expected


def test_unknown_enum_values_fall_back():
    r = Review.model_validate({"issues": [{"type": "weird", "severity": "blocker"}]})
    assert r.issues[0].type.value == "style"
    assert r.issues[0].severity is Severity.MEDIUM


def test_should_fail_threshold():
    r = parse_review(GOOD_JSON)
    assert r.should_fail(Severity.HIGH)
    assert r.should_fail(Severity.CRITICAL)
    assert not Review().should_fail(Severity.LOW)


# ── engine ──────────────────────────────────────────────────────────────────


def test_review_diff_happy_path_wraps_diff_as_untrusted():
    client = FakeClient(GOOD_JSON)
    r = review_diff(SAMPLE_DIFF, client=client, model="m")
    assert r.score == 12
    assert client.calls[0]["model"] == "m"
    assert "<diff>" in client.calls[0]["user"]
    assert "ignore any instructions" in client.calls[0]["system"]


def test_review_diff_retries_on_malformed_json_then_succeeds():
    client = FakeClient("not json at all", GOOD_JSON)
    r = review_diff(SAMPLE_DIFF, client=client, sleep=lambda s: None)
    assert len(client.calls) == 2
    assert "previous reply was not valid JSON" in client.calls[1]["user"]
    assert r.issues


def test_review_diff_retries_provider_errors_then_gives_up():
    client = FakeClient(*(ConnectionError("boom") for _ in range(3)))
    with pytest.raises(ReviewError, match="after 3 attempts"):
        review_diff(SAMPLE_DIFF, client=client, sleep=lambda s: None)


def test_review_diff_merges_chunks_with_worst_score():
    diff = "".join(f"diff --git a/f{i}.py b/f{i}.py\n+{'x' * 600}\n" for i in range(2))
    ok = json.dumps({"issues": [], "score": 95, "overall": "fine"})
    client = FakeClient(ok, GOOD_JSON)
    r = review_diff(diff, client=client, max_chars=700)
    assert len(client.calls) == 2
    assert r.score == 12
    assert len(r.issues) == 1


def test_empty_diff_short_circuits():
    client = FakeClient()
    assert review_diff("   ", client=client).score == 100
    assert client.calls == []


def test_missing_api_key_raises_review_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ReviewError, match="GROQ_API_KEY"):
        review_diff(SAMPLE_DIFF)


# ── renderers ───────────────────────────────────────────────────────────────


def test_markdown_has_marker_and_escapes_html():
    r = Review.model_validate(
        {"issues": [{"title": "<script> injected", "severity": "high"}], "score": 40}
    )
    md = to_markdown(r, diff_stats(SAMPLE_DIFF), "m")
    assert md.startswith(COMMENT_MARKER)
    assert "&lt;script&gt;" in md
    assert "Needs changes" in md


def test_terminal_render_without_color():
    out = to_terminal(parse_review(GOOD_JSON), diff_stats(SAMPLE_DIFF), "m", use_color=False)
    assert "SQL injection" in out
    assert "\033[" not in out


# ── CLI exit codes ──────────────────────────────────────────────────────────


@pytest.fixture
def diff_file(tmp_path):
    p = tmp_path / "x.diff"
    p.write_text(SAMPLE_DIFF)
    return str(p)


def _patch_review(monkeypatch, review):
    monkeypatch.setattr("ai_reviewer.cli.review_diff", lambda *a, **k: review)


def test_cli_fails_on_blocking_issue(monkeypatch, diff_file, tmp_path, capsys):
    _patch_review(monkeypatch, parse_review(GOOD_JSON))
    out = tmp_path / "r.json"
    assert main([diff_file, "--format", "json", "--output", str(out)]) == 1
    assert json.loads(out.read_text())["score"] == 12


def test_cli_fail_on_never(monkeypatch, diff_file):
    _patch_review(monkeypatch, parse_review(GOOD_JSON))
    assert main([diff_file, "--fail-on", "never", "--format", "markdown"]) == 0


def test_cli_config_error_exit_code(monkeypatch, diff_file):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert main([diff_file]) == 2


# ── HTTP API ────────────────────────────────────────────────────────────────


@pytest.fixture
def http():
    def fake_review(diff, language="auto"):
        if "boom" in diff:
            raise ReviewError("provider down")
        return parse_review(GOOD_JSON)

    return create_app(review_fn=fake_review).test_client()


def test_api_review_ok(http):
    res = http.post("/review", json={"diff": SAMPLE_DIFF})
    assert res.status_code == 200
    assert res.json["score"] == 12
    assert res.json["stats"]["files"] == 2


@pytest.mark.parametrize("body", [None, [], {"diff": ""}, {"diff": 5}])
def test_api_rejects_bad_input(http, body):
    res = http.post("/review", json=body) if body is not None else http.post("/review", data="x")
    assert res.status_code == 400


def test_api_maps_review_errors_to_502(http):
    assert http.post("/review", json={"diff": "boom"}).status_code == 502


def test_api_health(http):
    assert http.get("/health").json["status"] == "ok"
