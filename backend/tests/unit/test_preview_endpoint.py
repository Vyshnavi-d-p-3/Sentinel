"""Preview review API — runs full pipeline with mock LLM (no API keys)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,4 @@
 def login(user, password):
+    # placeholder: hash password in production
     return user"""


def test_preview_review_returns_structured_output():
    r = client.post(
        "/api/v1/reviews/preview",
        json={
            "repo_id": "unit-test",
            "pr_number": 42,
            "pr_title": "Add login",
            "diff": SAMPLE_DIFF,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "summary" in data
    assert "comments" in data
    assert isinstance(data["comments"], list)
    assert data["comments"][0]["file_path"] == "src/auth.py"


def test_preview_rejects_nondiff_body():
    r = client.post(
        "/api/v1/reviews/preview",
        json={"diff": "not a real diff with file headers"},
    )
    assert r.status_code == 400


def test_preview_rejects_empty_diff_422():
    r = client.post("/api/v1/reviews/preview", json={"diff": ""})
    assert r.status_code == 422
