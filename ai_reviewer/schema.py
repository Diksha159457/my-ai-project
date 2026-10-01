"""Typed review schema.

LLMs return *almost* the JSON you asked for. These models normalise the common
drift (upper-case enums, string scores, missing fields) so the rest of the code
can rely on clean, typed data instead of defensive ``dict.get`` chains.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class IssueType(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]


_TYPE_ALIASES = {"perf": "performance", "sec": "security", "vulnerability": "security"}


class Issue(BaseModel):
    type: IssueType = IssueType.STYLE
    severity: Severity = Severity.MEDIUM
    title: str = "Untitled issue"
    line: str = ""
    description: str = ""
    fix: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def _norm_type(cls, v: Any) -> str:
        v = str(v or "style").strip().lower()
        v = _TYPE_ALIASES.get(v, v)
        return v if v in IssueType._value2member_map_ else "style"

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v: Any) -> str:
        v = str(v or "medium").strip().lower()
        return v if v in Severity._value2member_map_ else "medium"

    @field_validator("line", "description", "fix", "title", mode="before")
    @classmethod
    def _stringify(cls, v: Any) -> str:
        return "" if v is None else str(v)


class Review(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)
    overall: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v: Any) -> int:
        try:
            return max(0, min(100, round(float(v))))
        except (TypeError, ValueError):
            return 0

    def counts(self) -> dict[str, int]:
        out = {t.value: 0 for t in IssueType}
        for issue in self.issues:
            out[issue.type.value] += 1
        return out

    def max_severity(self) -> Severity | None:
        if not self.issues:
            return None
        return max((i.severity for i in self.issues), key=lambda s: s.rank)

    def should_fail(self, threshold: Severity) -> bool:
        """True if any issue is at or above ``threshold`` severity."""
        return any(i.severity.rank >= threshold.rank for i in self.issues)

    @classmethod
    def merge(cls, reviews: list[Review]) -> Review:
        """Combine per-chunk reviews: concatenate issues, take the worst score."""
        if not reviews:
            return cls(score=100, overall="Nothing to review.")
        if len(reviews) == 1:
            return reviews[0]
        return cls(
            issues=[i for r in reviews for i in r.issues],
            score=min(r.score for r in reviews),
            overall=" ".join(r.overall for r in reviews if r.overall),
        )
