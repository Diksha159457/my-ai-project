"""Unified-diff helpers: stats, per-file splitting and token-budget chunking.

Large PRs blow past the model's context window. Instead of truncating blindly,
we split the diff at file boundaries and pack files into chunks under a
character budget, so each request sees complete hunks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)

# Lock files and generated assets add tokens but no review value.
DEFAULT_IGNORES = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    ".min.js",
    ".min.css",
    ".svg",
    ".ipynb",
)


@dataclass(frozen=True)
class DiffStats:
    files: int
    additions: int
    deletions: int

    @property
    def lines_changed(self) -> int:
        return self.additions + self.deletions


def diff_stats(diff: str) -> DiffStats:
    adds = dels = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            adds += 1
        elif line.startswith("-"):
            dels += 1
    return DiffStats(files=len(_FILE_HEADER.findall(diff)), additions=adds, deletions=dels)


def split_files(diff: str) -> list[tuple[str, str]]:
    """Return ``[(path, file_diff), ...]``. A diff with no headers is one blob."""
    matches = list(_FILE_HEADER.finditer(diff))
    if not matches:
        return [("<diff>", diff)] if diff.strip() else []
    out = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(diff)
        out.append((m.group(2), diff[m.start() : end]))
    return out


def chunk_diff(
    diff: str,
    max_chars: int = 24_000,
    ignore: tuple[str, ...] = DEFAULT_IGNORES,
) -> list[str]:
    """Pack per-file diffs into chunks no larger than ``max_chars``.

    A single file larger than the budget is hard-split on line boundaries so
    no chunk ever exceeds the limit.
    """
    chunks: list[str] = []
    current = ""
    for path, body in split_files(diff):
        if path.endswith(ignore):
            continue
        pieces = [body] if len(body) <= max_chars else _hard_split(body, max_chars)
        for piece in pieces:
            if current and len(current) + len(piece) > max_chars:
                chunks.append(current)
                current = ""
            current += piece
    if current.strip():
        chunks.append(current)
    return chunks


def _hard_split(text: str, max_chars: int) -> list[str]:
    parts, buf = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > max_chars:  # pathological single line
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(line[:max_chars])
            line = line[max_chars:]
        if len(buf) + len(line) > max_chars:
            parts.append(buf)
            buf = ""
        buf += line
    if buf:
        parts.append(buf)
    return parts
