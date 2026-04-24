from app.models.review_output import CommentCategory, Severity
from app.services.mock_label_anchor import category_severity_for_anchor


def test_anchor_is_stable_across_runs() -> None:
    a = category_severity_for_anchor("src/a.py", 10)
    b = category_severity_for_anchor("src/a.py", 10)
    assert a == b
    assert isinstance(a[0], CommentCategory)
    assert isinstance(a[1], Severity)


def test_distinct_anchors_can_differ() -> None:
    # High probability: two random anchors differ on at least one of category/severity.
    pairs = {category_severity_for_anchor(f"f{i}.py", i) for i in range(40)}
    categories = {p[0] for p in pairs}
    assert len(categories) >= 2
