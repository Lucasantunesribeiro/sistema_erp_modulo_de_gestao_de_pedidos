"""Testes E2E de autenticação usando Playwright."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e]


def test_login_success_returns_tokens(api_request_context, auth_credentials):
    username, password = auth_credentials

    response = api_request_context.post(
        "/api/v1/auth/token/",
        data={"username": username, "password": password},
    )

    assert response.status == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data


def test_login_invalid_password_returns_401(api_request_context, auth_credentials):
    username, _ = auth_credentials

    response = api_request_context.post(
        "/api/v1/auth/token/",
        data={"username": username, "password": "senha-errada"},
    )

    assert response.status == 401
