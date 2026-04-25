"""Unit tests for Step 5 Smart Test Generator."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("LLM_MOCK_MODE", "true")

from app.models import test_output as test_models  # noqa: E402
from app.models.review_output import CommentCategory, ReviewComment, Severity  # noqa: E402
from app.services.test_generator import TestGenerator  # noqa: E402


def test_generated_test_and_output_models_validate() -> None:
    item = test_models.GeneratedTest(
        comment_title="SQL injection",
        file_path="app/db.py",
        test_file_path="tests/test_db.py",
        framework=test_models.TestFramework.PYTEST,
        test_code="def test_sql_injection():\n    assert True\n",
        test_name="test_sql_injection",
        description="Verifies unsafe query handling",
        category=CommentCategory.SECURITY,
        setup_notes="No setup",
        confidence=0.9,
    )
    payload = test_models.TestGenerationOutput(
        tests=[item],
        total_comments_eligible=1,
        total_tests_generated=1,
        skipped_reasons=[],
    )
    assert payload.tests[0].framework == test_models.TestFramework.PYTEST
    assert payload.total_tests_generated == 1


def test_eligibility_filtering() -> None:
    generator = TestGenerator()
    secure_critical = ReviewComment(
        file_path="app/db.py",
        line_number=10,
        category=CommentCategory.SECURITY,
        severity=Severity.CRITICAL,
        title="Unsafe SQL",
        body="Interpolated SQL string",
        suggestion="Use parameterized query",
        confidence=0.9,
    )
    style_low = ReviewComment(
        file_path="README.md",
        line_number=1,
        category=CommentCategory.STYLE,
        severity=Severity.LOW,
        title="Docs style",
        body="Minor copy tweak",
        suggestion=None,
        confidence=0.5,
    )
    assert generator._is_eligible(secure_critical) is True
    assert generator._is_eligible(style_low) is False


@pytest.mark.asyncio
async def test_no_eligible_comments_returns_empty_result() -> None:
    generator = TestGenerator()
    result = await generator.generate(
        "Docs update",
        [
            ReviewComment(
                file_path="README.md",
                line_number=1,
                category=CommentCategory.STYLE,
                severity=Severity.LOW,
                title="Style only",
                body="No behavior risk",
                suggestion=None,
                confidence=0.5,
            )
        ],
        {"README.md": "diff --git a/README.md b/README.md\n"},
    )
    assert result.output.total_comments_eligible == 0
    assert result.output.total_tests_generated == 0
    assert result.usage.model_version == "skipped"


@pytest.mark.asyncio
async def test_eligible_comment_triggers_generation() -> None:
    generator = TestGenerator()
    result = await generator.generate(
        "Fix SQL injection",
        [
            ReviewComment(
                file_path="app/db.py",
                line_number=9,
                category=CommentCategory.SECURITY,
                severity=Severity.HIGH,
                title="Unsafe query",
                body="Interpolated SQL with user input",
                suggestion="Use parameterized query",
                confidence=0.9,
            )
        ],
        {"app/db.py": "diff --git a/app/db.py b/app/db.py\n@@ -1,1 +1,1 @@\n"},
    )
    assert result.error is None
    assert result.output.total_comments_eligible >= 1
    assert result.output.total_tests_generated >= 1


@pytest.mark.asyncio
async def test_mixed_comments_are_filtered_before_generation() -> None:
    generator = TestGenerator()
    result = await generator.generate(
        "Mixed findings",
        [
            ReviewComment(
                file_path="app/db.py",
                line_number=9,
                category=CommentCategory.BUG,
                severity=Severity.MEDIUM,
                title="Logic bug",
                body="Broken branch condition",
                suggestion="Adjust branch",
                confidence=0.8,
            ),
            ReviewComment(
                file_path="README.md",
                line_number=1,
                category=CommentCategory.SUGGESTION,
                severity=Severity.HIGH,
                title="Rewrite docs",
                body="Copy update",
                suggestion=None,
                confidence=0.6,
            ),
        ],
        {"app/db.py": "diff --git a/app/db.py b/app/db.py\n@@ -1,1 +1,1 @@\n"},
    )
    assert result.output.total_comments_eligible == 1
