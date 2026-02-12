"""Integration tests for Order API endpoints.

Covers:
- Order creation via POST /api/v1/orders/.
- Order list via GET /api/v1/orders/.
- Order retrieve via GET /api/v1/orders/{id}/.
- Status update via PATCH /api/v1/orders/{id}/.
- Domain exception mapping (400, 404, 422).
- Authentication enforcement (401 without token).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.integration

User = get_user_model()

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="orderuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="API Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="api-order@example.com",
        is_active=True,
    )


@pytest.fixture()
def inactive_customer():
    return Customer.objects.create(
        name="Inactive API Customer",
        document="11222333000181",
        document_type=DocumentType.CNPJ,
        email="inactive-api@example.com",
        is_active=False,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="API-PROD-A",
        name="API Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="API-PROD-B",
        name="API Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def inactive_product():
    return Product.objects.create(
        sku="API-INACTIVE",
        name="Inactive API Product",
        price=Decimal("5.00"),
        stock_quantity=10,
        status=ProductStatus.INACTIVE,
    )


@pytest.fixture()
def low_stock_product():
    return Product.objects.create(
        sku="API-LOW",
        name="Low Stock API Product",
        price=Decimal("15.00"),
        stock_quantity=2,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def order_payload(customer, product_a, product_b):
    return {
        "customer_id": str(customer.id),
        "items": [
            {"product_id": str(product_a.id), "quantity": 2},
            {"product_id": str(product_b.id), "quantity": 1},
        ],
        "notes": "API test order",
    }


@pytest.fixture()
def created_order(auth_client, order_payload):
    """Create an order via the API and return the response data."""
    response = auth_client.post("/api/v1/orders/", order_payload, format="json")
    assert response.status_code == 201
    return response.data


# ===========================================================================
# Authentication
# ===========================================================================


class TestOrderAPIAuth:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/orders/")
        assert response.status_code == 401

    def test_unauthenticated_post_returns_401(self, api_client):
        response = api_client.post("/api/v1/orders/", {}, format="json")
        assert response.status_code == 401


# ===========================================================================
# CREATE
# ===========================================================================


class TestOrderCreate:
    def test_create_success(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")

        assert response.status_code == 201
        data = response.data
        assert data["status"] == OrderStatus.PENDING
        assert data["order_number"].startswith("ORD-")
        assert len(data["items"]) == 2
        assert data["notes"] == "API test order"
        assert Decimal(data["total_amount"]) == Decimal("45.50")

    def test_create_deducts_stock(
        self, auth_client, order_payload, product_a, product_b
    ):
        auth_client.post("/api/v1/orders/", order_payload, format="json")

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 98
        assert product_b.stock_quantity == 49

    def test_create_customer_not_found_returns_404(self, auth_client, product_a):
        payload = {
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 404

    def test_create_inactive_customer_returns_400(
        self, auth_client, inactive_customer, product_a
    ):
        payload = {
            "customer_id": str(inactive_customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_create_product_not_found_returns_404(self, auth_client, customer):
        payload = {
            "customer_id": str(customer.id),
            "items": [
                {
                    "product_id": "00000000-0000-0000-0000-000000000000",
                    "quantity": 1,
                }
            ],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 404

    def test_create_inactive_product_returns_400(
        self, auth_client, customer, inactive_product
    ):
        payload = {
            "customer_id": str(customer.id),
            "items": [
                {"product_id": str(inactive_product.id), "quantity": 1},
            ],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_create_insufficient_stock_returns_422(
        self, auth_client, customer, low_stock_product
    ):
        payload = {
            "customer_id": str(customer.id),
            "items": [
                {"product_id": str(low_stock_product.id), "quantity": 10},
            ],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 422

    def test_create_empty_items_returns_400(self, auth_client, customer):
        payload = {
            "customer_id": str(customer.id),
            "items": [],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_create_missing_customer_id_returns_400(self, auth_client, product_a):
        payload = {
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400


# ===========================================================================
# LIST
# ===========================================================================


class TestOrderList:
    def test_list_empty(self, auth_client):
        response = auth_client.get("/api/v1/orders/")
        assert response.status_code == 200
        assert response.data["results"] == []
        assert response.data["count"] == 0

    def test_list_returns_orders(self, auth_client, created_order):
        response = auth_client.get("/api/v1/orders/")
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert (
            response.data["results"][0]["order_number"] == created_order["order_number"]
        )

    def test_list_filter_by_status(self, auth_client, created_order):
        response = auth_client.get("/api/v1/orders/", {"status": OrderStatus.PENDING})
        assert response.status_code == 200
        assert response.data["count"] == 1

        response = auth_client.get("/api/v1/orders/", {"status": OrderStatus.CONFIRMED})
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_list_filter_by_customer(self, auth_client, created_order, customer):
        response = auth_client.get("/api/v1/orders/", {"customer_id": str(customer.id)})
        assert response.status_code == 200
        assert response.data["count"] == 1


# ===========================================================================
# RETRIEVE
# ===========================================================================


class TestOrderRetrieve:
    def test_retrieve_success(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.get(f"/api/v1/orders/{order_id}/")
        assert response.status_code == 200
        assert response.data["id"] == order_id
        assert len(response.data["items"]) == 2
        assert "status_history" in response.data

    def test_retrieve_not_found(self, auth_client):
        response = auth_client.get(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404


# ===========================================================================
# PATCH (Status Update)
# ===========================================================================


class TestOrderStatusUpdate:
    def test_update_status_success(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CONFIRMED, "notes": "Approved"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == OrderStatus.CONFIRMED

    def test_update_status_invalid_transition_returns_400(
        self, auth_client, created_order
    ):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.SHIPPED},
            format="json",
        )
        assert response.status_code == 400

    def test_update_status_order_not_found_returns_404(self, auth_client):
        response = auth_client.patch(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        assert response.status_code == 404

    def test_update_status_missing_status_returns_400(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"notes": "No status"},
            format="json",
        )
        assert response.status_code == 400

    def test_full_lifecycle_via_api(self, auth_client, created_order):
        order_id = created_order["id"]

        for next_status in [
            OrderStatus.CONFIRMED,
            OrderStatus.SEPARATED,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
        ]:
            response = auth_client.patch(
                f"/api/v1/orders/{order_id}/",
                {"status": next_status},
                format="json",
            )
            assert response.status_code == 200
            assert response.data["status"] == next_status
