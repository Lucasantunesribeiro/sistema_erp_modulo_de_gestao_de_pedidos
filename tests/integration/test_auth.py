"""Integration tests for Auth0 JWT authentication.

Validates:
  - /health is public (AllowAny — plain Django view, no DRF).
  - Protected DRF endpoints return 401 without a token.
  - Protected DRF endpoints return 401 with an invalid token.
  - Protected DRF endpoints return 401 with a malformed Authorization header.
"""

import pytest

pytestmark = pytest.mark.integration


class TestPublicEndpoints:
    """Health check must remain accessible without credentials."""

    def test_health_is_public(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestProtectedEndpoints:
    """All DRF endpoints require a valid JWT by default (Fail Closed)."""

    def test_no_token_returns_401(self, api_client):
        response = api_client.get("/api/v1/me")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        response = api_client.get("/api/v1/me")
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Token some-token")
        response = api_client.get("/api/v1/me")
        assert response.status_code == 401

    def test_empty_bearer_returns_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer ")
        response = api_client.get("/api/v1/me")
        assert response.status_code == 401

    def test_401_includes_www_authenticate_header(self, api_client):
        response = api_client.get("/api/v1/me")
        assert response.status_code == 401
        assert "Bearer" in response.get("WWW-Authenticate", "")
