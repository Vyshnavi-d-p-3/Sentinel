"""
Tests for the API-key dependency.

The dependency is a no-op when ``settings.api_key`` is empty (open API mode),
and otherwise enforces ``X-API-Key`` or ``Authorization: Bearer`` with a
constant-time compare. We monkey-patch the module-level ``settings`` reference
to flip between modes within a single test run.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import auth as auth_module


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(auth_module.require_api_key)])
    async def protected():
        return {"ok": True}

    return app


def test_open_mode_when_api_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "")
    resp = TestClient(_make_app()).get("/protected")
    assert resp.status_code == 200


def test_rejects_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "secret-token")
    resp = TestClient(_make_app()).get("/protected")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_accepts_x_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "secret-token")
    resp = TestClient(_make_app()).get(
        "/protected", headers={"X-API-Key": "secret-token"}
    )
    assert resp.status_code == 200


def test_accepts_bearer_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "secret-token")
    resp = TestClient(_make_app()).get(
        "/protected", headers={"Authorization": "Bearer secret-token"}
    )
    assert resp.status_code == 200


def test_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "secret-token")
    resp = TestClient(_make_app()).get(
        "/protected", headers={"X-API-Key": "not-the-key"}
    )
    assert resp.status_code == 401


def test_non_bearer_authorization_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module.settings, "api_key", "secret-token")
    resp = TestClient(_make_app()).get(
        "/protected", headers={"Authorization": "Basic xyz"}
    )
    assert resp.status_code == 401
