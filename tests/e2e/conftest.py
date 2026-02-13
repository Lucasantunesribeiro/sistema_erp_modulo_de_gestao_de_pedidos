"""E2E test fixtures for Playwright.

The pytest-playwright plugin automatically provides:
  - page: A new browser page for each test
  - context: A new browser context for each test
  - browser: A browser instance (session scope)

Override base_url with --base-url on the CLI:
    pytest -m e2e --base-url http://localhost:8000
"""

from __future__ import annotations

import subprocess
from typing import Generator
from uuid import uuid4

import pytest
from playwright.sync_api import APIRequestContext, Playwright


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """Provide base URL for Playwright tests.

    Uses --base-url CLI value if given, otherwise defaults to the
    Django dev server running inside the Docker container.
    """
    return request.config.getoption("base_url") or "http://localhost:8000"


@pytest.fixture(autouse=True)
def _use_db() -> None:
    """Override root conftest _use_db — e2e tests hit the server over HTTP,
    they do not need the pytest-django ``db`` fixture (which conflicts
    with Playwright's async event-loop)."""


@pytest.fixture(scope="session")
def api_request_context(
    playwright: Playwright, base_url: str
) -> Generator[APIRequestContext, None, None]:
    """Contexto de API do Playwright para chamadas HTTP diretas."""
    context = playwright.request.new_context(base_url=base_url)
    yield context
    context.dispose()


def _run_manage_py(command: str) -> None:
    subprocess.run(
        ["python", "src/manage.py", "shell", "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )


def _create_user(username: str, password: str) -> None:
    command = (
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        f"User.objects.filter(username={username!r}).delete(); "
        f"User.objects.create_user(username={username!r}, password={password!r})"
    )
    _run_manage_py(command)


def _delete_user(username: str) -> None:
    command = (
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        f"User.objects.filter(username={username!r}).delete()"
    )
    _run_manage_py(command)


@pytest.fixture()
def auth_credentials() -> Generator[tuple[str, str], None, None]:
    """Cria um usuário de teste e retorna credenciais válidas."""
    username = f"e2euser_{uuid4().hex[:8]}"
    password = "testpass123"
    _create_user(username, password)
    try:
        yield username, password
    finally:
        _delete_user(username)


@pytest.fixture()
def auth_token(api_request_context, auth_credentials) -> str:
    """Obtém token JWT para autenticação nos testes E2E."""
    username, password = auth_credentials
    response = api_request_context.post(
        "/api/v1/auth/token/",
        data={"username": username, "password": password},
    )
    assert response.status == 200
    data = response.json()
    return data["access"]
