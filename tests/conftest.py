import pytest

from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _use_db(db):
    """Automatically use the test database for all tests."""


@pytest.fixture()
def api_client():
    """DRF APIClient for testing API endpoints."""
    return APIClient()


@pytest.fixture()
def api_client_with_correlation(api_client):
    """APIClient pre-configured with a known correlation ID header."""
    cid = "test-correlation-id-fixture"
    api_client.defaults["HTTP_X_REQUEST_ID"] = cid
    return api_client, cid
