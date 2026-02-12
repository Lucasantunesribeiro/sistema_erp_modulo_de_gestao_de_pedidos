"""Integration tests for Product API endpoints.

Covers:
- CRUD operations via /api/v1/products/.
- Domain exception mapping (404, 409).
- Authentication enforcement (401 without token).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.products.models import Product

pytestmark = pytest.mark.integration

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
def sample_product():
    """A persisted Product instance."""
    product = Product(
        sku="SKU-001",
        name="Widget Alpha",
        description="A fine widget",
        price=Decimal("19.99"),
        stock_quantity=100,
    )
    product.save()
    return product


# ===========================================================================
# Authentication
# ===========================================================================


class TestProductAPIAuth:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/products/")
        assert response.status_code == 401


# ===========================================================================
# LIST
# ===========================================================================


class TestProductList:
    def test_list_empty(self, auth_client):
        response = auth_client.get("/api/v1/products/")
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_list_returns_products(self, auth_client, sample_product):
        response = auth_client.get("/api/v1/products/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Widget Alpha"


# ===========================================================================
# RETRIEVE
# ===========================================================================


class TestProductRetrieve:
    def test_retrieve_success(self, auth_client, sample_product):
        response = auth_client.get(f"/api/v1/products/{sample_product.id}/")
        assert response.status_code == 200
        assert response.data["name"] == "Widget Alpha"
        assert response.data["id"] == str(sample_product.id)
        assert response.data["sku"] == "SKU-001"

    def test_retrieve_not_found(self, auth_client):
        response = auth_client.get(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404


# ===========================================================================
# CREATE
# ===========================================================================


class TestProductCreate:
    def test_create_success(self, auth_client):
        payload = {
            "sku": "SKU-NEW",
            "name": "New Product",
            "price": "29.99",
            "description": "Brand new",
            "stock_quantity": 50,
        }
        response = auth_client.post("/api/v1/products/", payload, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "New Product"
        assert response.data["sku"] == "SKU-NEW"
        assert "id" in response.data

    def test_create_duplicate_sku_returns_409(self, auth_client, sample_product):
        payload = {
            "sku": "SKU-001",
            "name": "Duplicate",
            "price": "9.99",
        }
        response = auth_client.post("/api/v1/products/", payload, format="json")
        assert response.status_code == 409

    def test_create_missing_fields_returns_400(self, auth_client):
        payload = {"name": "Incomplete"}
        response = auth_client.post("/api/v1/products/", payload, format="json")
        assert response.status_code == 400

    def test_create_invalid_price_returns_400(self, auth_client):
        payload = {
            "sku": "SKU-BAD",
            "name": "Bad Price",
            "price": "-5.00",
        }
        response = auth_client.post("/api/v1/products/", payload, format="json")
        assert response.status_code == 400


# ===========================================================================
# UPDATE
# ===========================================================================


class TestProductUpdate:
    def test_update_success(self, auth_client, sample_product):
        payload = {"name": "Widget Updated"}
        response = auth_client.patch(
            f"/api/v1/products/{sample_product.id}/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["name"] == "Widget Updated"

    def test_update_not_found(self, auth_client):
        payload = {"name": "Ghost"}
        response = auth_client.patch(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/",
            payload,
            format="json",
        )
        assert response.status_code == 404

    def test_put_update_success(self, auth_client, sample_product):
        payload = {
            "name": "Widget PUT",
            "price": "25.00",
            "description": "Updated via PUT",
            "stock_quantity": 200,
        }
        response = auth_client.put(
            f"/api/v1/products/{sample_product.id}/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["name"] == "Widget PUT"

    def test_update_status(self, auth_client, sample_product):
        payload = {"status": "inactive"}
        response = auth_client.patch(
            f"/api/v1/products/{sample_product.id}/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["status"] == "inactive"


# ===========================================================================
# DESTROY
# ===========================================================================


class TestProductDestroy:
    def test_destroy_success(self, auth_client, sample_product):
        response = auth_client.delete(f"/api/v1/products/{sample_product.id}/")
        assert response.status_code == 204
        # Verify soft-deleted
        sample_product.refresh_from_db()
        assert sample_product.deleted_at is not None

    def test_destroy_not_found(self, auth_client):
        response = auth_client.delete(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404
