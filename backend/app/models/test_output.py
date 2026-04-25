"""Structured output schemas for Step 5 Smart Test Generator."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.review_output import CommentCategory


class TestFramework(str, Enum):
    PYTEST = "pytest"
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    UNITTEST = "unittest"


class GeneratedTest(BaseModel):
    """One generated runnable regression test."""

    comment_title: str = Field(description="Title of the finding this test targets")
    file_path: str = Field(description="Source file path for the finding")
    test_file_path: str = Field(description="Suggested test file path")
    framework: TestFramework
    test_code: str = Field(description="Runnable test code")
    test_name: str = Field(description="Stable test name")
    description: str = Field(description="What behavior this test validates and why")
    category: CommentCategory
    setup_notes: str = Field(default="", description="Extra setup notes for running the test")
    confidence: float = Field(ge=0.0, le=1.0)


class TestGenerationOutput(BaseModel):
    """Step 5 output containing generated tests and skip metadata."""

    tests: list[GeneratedTest] = Field(default_factory=list)
    total_comments_eligible: int = Field(ge=0)
    total_tests_generated: int = Field(ge=0)
    skipped_reasons: list[str] = Field(default_factory=list)
