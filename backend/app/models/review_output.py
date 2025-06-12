"""
Structured output schema for LLM-generated code reviews.

Pydantic v2 models enforce type safety on LLM JSON responses and
enable automated evaluation scoring via the eval harness.
"""

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


class ReviewOutput(BaseModel):
    """Complete structured review from the LLM. Enforced via JSON mode."""

    summary: str = Field(description="2-3 sentence PR assessment")
    comments: list[ReviewComment] = Field(default_factory=list)
    pr_quality_score: float = Field(ge=0.0, le=10.0)
    review_focus_areas: list[str] = Field(description="Key areas for human reviewers")
