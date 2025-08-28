"""
Structured output schema for LLM-generated code reviews.

Pydantic v2 models enforce type safety on LLM JSON responses and
enable automated evaluation scoring via the eval harness.

The agentic pipeline produces four distinct structured outputs:
- ``TriageReport``        — file-level risk classification (step 1)
- ``FileReviewOutput``    — per-file deep review comments (step 2)
- ``CrossReferenceOutput``— multi-file issue detection (step 3)
- ``ReviewSynthesis``     — final summary, quality score, focus areas (step 4)

These are aggregated by the orchestrator into a single ``ReviewOutput``
that downstream persistence and dashboard code consume.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CommentCategory(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    STYLE = "style"
    SUGGESTION = "suggestion"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FileRisk(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SKIP = "skip"


class FileTriageItem(BaseModel):
    """One file's triage classification (step 1 output)."""

    file_path: str
    risk: FileRisk
    reasoning: str = Field(description="Why this file got this risk level")
    lines_changed: int = Field(ge=0)


class TriageReport(BaseModel):
    """Complete file-triage output for one PR."""

    files: list[FileTriageItem] = Field(default_factory=list)
    total_files: int = Field(ge=0)
    files_to_review: int = Field(ge=0, description="Count of high+medium risk files")


class ReviewComment(BaseModel):
    """A single review comment anchored to a specific file and line."""

    file_path: str = Field(description="Path to the file being reviewed")
    line_number: int = Field(description="Line number the comment refers to")
    category: CommentCategory
    severity: Severity
    title: str = Field(description="One-line summary", max_length=120)
    body: str = Field(description="Detailed explanation of the issue")
    suggestion: str | None = Field(None, description="Concrete fix suggestion")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence")
    related_files: list[str] = Field(
        default_factory=list,
        description="Other files involved (populated for cross-file findings)",
    )


class FileReviewOutput(BaseModel):
    """Per-file deep review output (step 2)."""

    file_path: str
    comments: list[ReviewComment] = Field(default_factory=list)


class CrossReferenceOutput(BaseModel):
    """Multi-file issue detection output (step 3)."""

    comments: list[ReviewComment] = Field(default_factory=list)


class ReviewSynthesis(BaseModel):
    """Final synthesis output (step 4)."""

    summary: str = Field(description="2-3 sentence PR assessment")
    pr_quality_score: float = Field(ge=0.0, le=10.0)
    review_focus_areas: list[str] = Field(default_factory=list)


class ReviewOutput(BaseModel):
    """Aggregated structured review consumed by persistence + dashboard."""

    summary: str = Field(description="2-3 sentence PR assessment")
    comments: list[ReviewComment] = Field(default_factory=list)
    pr_quality_score: float = Field(ge=0.0, le=10.0)
    review_focus_areas: list[str] = Field(description="Key areas for human reviewers")
