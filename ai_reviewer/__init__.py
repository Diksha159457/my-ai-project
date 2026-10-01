"""AI Code Review Assistant — LLM-powered review of git diffs."""

from .diff import DiffStats, chunk_diff, diff_stats
from .engine import ReviewError, review_diff
from .schema import Issue, Review

__all__ = [
    "DiffStats",
    "Issue",
    "Review",
    "ReviewError",
    "chunk_diff",
    "diff_stats",
    "review_diff",
]
__version__ = "3.0.0"
