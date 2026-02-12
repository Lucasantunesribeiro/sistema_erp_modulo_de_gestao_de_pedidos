"""Integration tests for Customer API endpoints.

Covers:
- CRUD operations via /api/v1/customers/.
- Domain exception mapping (404, 409).
- Authentication enforcement (401 without token).
"""

from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType

pytestmark = pytest.mark.integration

VALID_CPF = "59860184275"
VALID_CNPJ = "11222333000181"

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def sample_customer():
    """A persisted Customer instance."""
    customer = Customer(
        name="João Silva",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="joao@example.com",
    )
    customer.save()
    return customer


# ===========================================================================
# Authentication
# ===========================================================================


class TestCustomerAPIAuth:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/customers/")
        assert response.status_code == 401


# ===========================================================================
# LIST
# ===========================================================================


class TestCustomerList:
    def test_list_empty(self, auth_client):
        response = auth_client.get("/api/v1/customers/")
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_list_returns_customers(self, auth_client, sample_customer):
        response = auth_client.get("/api/v1/customers/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "João Silva"


# ===========================================================================
# RETRIEVE
# ===========================================================================


class TestCustomerRetrieve:
    def test_retrieve_success(self, auth_client, sample_customer):
        response = auth_client.get(f"/api/v1/customers/{sample_customer.id}/")
        assert response.status_code == 200
        assert response.data["name"] == "João Silva"
        assert response.data["id"] == str(sample_customer.id)

    def test_retrieve_not_found(self, auth_client):
        response = auth_client.get(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404


# ===========================================================================
# CREATE
# ===========================================================================


class TestCustomerCreate:
    def test_create_success(self, auth_client):
        payload = {
            "name": "Maria Souza",
            "document": VALID_CPF,
            "document_type": "CPF",
            "email": "maria@example.com",
        }
        response = auth_client.post("/api/v1/customers/", payload, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "Maria Souza"
        assert "id" in response.data

    def test_create_duplicate_document_returns_409(self, auth_client, sample_customer):
        payload = {
            "name": "Duplicate",
            "document": VALID_CPF,
            "document_type": "CPF",
            "email": "other@example.com",
        }
        response = auth_client.post("/api/v1/customers/", payload, format="json")
        assert response.status_code == 409

    def test_create_duplicate_email_returns_409(self, auth_client, sample_customer):
        payload = {
            "name": "Duplicate",
            "document": VALID_CNPJ,
            "document_type": "CNPJ",
            "email": "joao@example.com",
        }
        response = auth_client.post("/api/v1/customers/", payload, format="json")
        assert response.status_code == 409

    def test_create_missing_fields_returns_400(self, auth_client):
        payload = {"name": "Incomplete"}
        response = auth_client.post("/api/v1/customers/", payload, format="json")
        assert response.status_code == 400


# ===========================================================================
# UPDATE
# ===========================================================================


class TestCustomerUpdate:
    def test_update_success(self, auth_client, sample_customer):
        payload = {"name": "João Atualizado"}
        response = auth_client.patch(
            f"/api/v1/customers/{sample_customer.id}/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["name"] == "João Atualizado"

    def test_update_not_found(self, auth_client):
        payload = {"name": "Ghost"}
        response = auth_client.patch(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000/",
            payload,
            format="json",
        )
        assert response.status_code == 404

    def test_put_update_success(self, auth_client, sample_customer):
        payload = {
            "name": "João PUT",
            "document": VALID_CPF,
            "document_type": "CPF",
            "email": "joao@example.com",
        }
        response = auth_client.put(
            f"/api/v1/customers/{sample_customer.id}/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["name"] == "João PUT"


# ===========================================================================
# DESTROY
# ===========================================================================


class TestCustomerDestroy:
    def test_destroy_success(self, auth_client, sample_customer):
        response = auth_client.delete(f"/api/v1/customers/{sample_customer.id}/")
        assert response.status_code == 204
        # Verify soft-deleted
        sample_customer.refresh_from_db()
        assert sample_customer.deleted_at is not None

    def test_destroy_not_found(self, auth_client):
        response = auth_client.delete(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404
