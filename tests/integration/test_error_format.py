"""Integration tests for standardized error responses."""

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="errorformat", password="testpass123")
    client.force_authenticate(user=user)
    return client


class TestStandardizedErrors:
    def test_auth_error_has_standard_format(self, api_client):
        response = api_client.get("/api/v1/customers/")
        assert response.status_code == 401
        data = response.json()
        assert "type" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)
        assert data["errors"]
        assert "code" in data["errors"][0]
        assert "detail" in data["errors"][0]

    def test_validation_error_has_standard_format(self, auth_client):
        response = auth_client.post("/api/v1/customers/", data="{", content_type="application/json")
        assert response.status_code == 400
        data = response.json()
        assert "type" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)
