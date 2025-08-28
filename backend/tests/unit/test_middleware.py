"""
Unit + integration tests for the security middleware stack.

These tests build a tiny FastAPI app rather than booting the full Sentinel
application — keeps them fast, free of DB dependencies, and focused on the
behavior under test (request ID, security headers, body size cap).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import (
    DEFAULT_SECURITY_HEADERS,
    REQUEST_ID_HEADER,
    AccessLogMiddleware,
    BodySizeLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


def _make_app(max_body_bytes: int = 64) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.post("/echo")
    async def echo(body: dict):
        return body

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app())


def test_request_id_is_generated_when_absent(client: TestClient) -> None:
    resp = client.get("/ping")
    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid and len(rid) >= 16


def test_request_id_echoed_when_valid(client: TestClient) -> None:
    resp = client.get("/ping", headers={REQUEST_ID_HEADER: "abc-123_xyz"})
    assert resp.headers[REQUEST_ID_HEADER] == "abc-123_xyz"


def test_request_id_replaced_when_invalid(client: TestClient) -> None:
    """Header-injection vector: newlines and arbitrary symbols are dropped."""
    resp = client.get("/ping", headers={REQUEST_ID_HEADER: "bad id\nwith newline"})
    rid = resp.headers[REQUEST_ID_HEADER]
    assert rid != "bad id\nwith newline"
    assert "\n" not in rid


def test_security_headers_present(client: TestClient) -> None:
    resp = client.get("/ping")
    for key, value in DEFAULT_SECURITY_HEADERS.items():
        assert resp.headers.get(key) == value, f"{key} missing"


def test_security_headers_do_not_override_handler_value() -> None:
    """If a handler sets a header explicitly we should not stomp it."""
    app = _make_app()

    @app.get("/with-header")
    async def with_header():
        from fastapi.responses import Response

        return Response(
            "ok",
            headers={"Referrer-Policy": "no-referrer"},
        )

    resp = TestClient(app).get("/with-header")
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_body_size_rejects_oversized_content_length(client: TestClient) -> None:
    big_body = b"x" * 1_000
    resp = client.post(
        "/echo",
        content=big_body,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Request body too large"


def test_body_size_allows_small_payload() -> None:
    app = _make_app(max_body_bytes=2048)
    client = TestClient(app)
    resp = client.post("/echo", json={"a": 1})
    assert resp.status_code == 200
    assert resp.json() == {"a": 1}


def test_body_size_get_request_unaffected(client: TestClient) -> None:
    resp = client.get("/ping")
    assert resp.status_code == 200
