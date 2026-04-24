"""
Deterministic (file_path, line) → (category, severity) for the mock LLM.

Used by the LLM gateway stubs and by ``generate_synthetic_fixtures.py`` so
eval ground truth stays aligned with mock output. Stable across processes
(unlike ``hash(str)``).
"""

from __future__ import annotations

import hashlib

from app.models.review_output import CommentCategory, Severity

# Fixed order for reproducible indexing (do not use Enum iteration order).
_CATEGORIES: tuple[CommentCategory, ...] = (
    CommentCategory.SECURITY,
    CommentCategory.BUG,
    CommentCategory.PERFORMANCE,
    CommentCategory.STYLE,
    CommentCategory.SUGGESTION,
)
_SEVERITIES: tuple[Severity, ...] = (
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
)


def category_severity_for_anchor(file_path: str, line: int) -> tuple[CommentCategory, Severity]:
    """Map diff anchor to category/severity; same inputs always yield the same pair."""
    digest = hashlib.sha256(f"{file_path}\0{line}".encode()).digest()
    h = int.from_bytes(digest[:8], "big")
    cat = _CATEGORIES[h % len(_CATEGORIES)]
    sev = _SEVERITIES[(h // 13) % len(_SEVERITIES)]
    return cat, sev
