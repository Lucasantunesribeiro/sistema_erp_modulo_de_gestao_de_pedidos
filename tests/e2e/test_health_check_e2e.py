"""E2E smoke test for health check endpoint using Playwright.

Run with:
    pytest -m e2e --base-url http://localhost:8000

Requires:
    pip install pytest-playwright
    playwright install chromium
"""

import pytest

pytestmark = [pytest.mark.e2e]


def test_health_check_returns_json(page):
    """Verify the /health endpoint returns valid JSON with status field via browser."""
    page.goto("/health")

    # The browser should display the raw JSON response
    body_text = page.text_content("body")
    assert body_text is not None

    import json

    data = json.loads(body_text)
    assert data["status"] == "healthy"
    assert "services" in data
    assert "timestamp" in data


def test_health_check_response_has_correlation_id(page):
    """Verify that the /health response includes X-Request-ID header."""
    response = page.goto("/health")
    headers = response.headers
    assert "x-request-id" in headers
