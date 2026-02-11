"""E2E test fixtures for Playwright.

The pytest-playwright plugin automatically provides:
  - page: A new browser page for each test
  - context: A new browser context for each test
  - browser: A browser instance (session scope)

Override base_url with --base-url on the CLI:
    pytest -m e2e --base-url http://localhost:8000
"""

import pytest


@pytest.fixture(scope="session")
def base_url(request):
    """Provide base URL for Playwright tests.

    Uses --base-url CLI value if given, otherwise defaults to the
    Django dev server running inside the Docker container.
    """
    return request.config.getoption("base_url") or "http://localhost:8000"


@pytest.fixture(autouse=True)
def _use_db():
    """Override root conftest _use_db — e2e tests hit the server over HTTP,
    they do not need the pytest-django ``db`` fixture (which conflicts
    with Playwright's async event-loop)."""
