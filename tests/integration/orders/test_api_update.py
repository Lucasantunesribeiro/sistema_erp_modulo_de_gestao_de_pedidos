"""Integration tests for Order status update and cancel endpoints.

Covers:
- PATCH /api/v1/orders/{id}/ (status update):
  - Success: PENDING -> CONFIRMED.
  - Missing status field returns 400.
  - Attempting CANCELLED via PATCH returns 400 (must use /cancel/).
  - Invalid transition returns 400.
  - Non-existent order returns 404.
- POST /api/v1/orders/{id}/cancel/ (cancel action):
  - Success: cancels order, returns 200, releases stock.
  - Cancelling from forbidden state (SHIPPED/DELIVERED) returns 400.
  - Non-existent order returns 404.
- Authentication enforcement.
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
    client = APIClient()
    user = User.objects.create_user(username="updateuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Update Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="update-test@example.com",
        is_active=True,
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="UPD-PROD",
        name="Update Test Product",
        price=Decimal("20.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def order_payload(customer, product):
    return {
        "customer_id": str(customer.id),
        "items": [
            {"product_id": str(product.id), "quantity": 5},
        ],
        "notes": "Update test order",
    }


@pytest.fixture()
def created_order(auth_client, order_payload):
    """Create an order via the API and return the response data."""
    response = auth_client.post("/api/v1/orders/", order_payload, format="json")
    assert response.status_code == 201
    return response.data


# ===========================================================================
# PATCH — Status Update
# ===========================================================================


class TestPatchStatusSuccess:
    def test_patch_pending_to_confirmed(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CONFIRMED, "notes": "Approved by manager"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == OrderStatus.CONFIRMED

    def test_patch_returns_full_serializer(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        data = response.data
        assert "id" in data
        assert "items" in data
        assert "status_history" in data

    def test_patch_records_history(self, auth_client, created_order):
        order_id = created_order["id"]
        auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CONFIRMED, "notes": "History check"},
            format="json",
        )
        # Retrieve to check history
        response = auth_client.get(f"/api/v1/orders/{order_id}/")
        history = response.data["status_history"]
        # Should have at least: creation + confirmation
        assert len(history) >= 2


class TestPatchStatusValidation:
    def test_patch_missing_status_returns_400(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"notes": "No status field"},
            format="json",
        )
        assert response.status_code == 400
        assert "status" in response.data["detail"].lower()

    def test_patch_cancel_via_patch_returns_400(self, auth_client, created_order):
        """Attempting to set status to CANCELLED via PATCH must fail."""
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CANCELLED},
            format="json",
        )
        assert response.status_code == 400
        assert "/cancel/" in response.data["detail"]

    def test_patch_cancel_lowercase_via_patch_returns_400(
        self, auth_client, created_order
    ):
        """Case-insensitive guard: 'cancelled' should also be blocked."""
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": "cancelled"},
            format="json",
        )
        assert response.status_code == 400
        assert "/cancel/" in response.data["detail"]

    def test_patch_invalid_transition_returns_400(self, auth_client, created_order):
        """PENDING -> SHIPPED is not allowed."""
        order_id = created_order["id"]
        response = auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.SHIPPED},
            format="json",
        )
        assert response.status_code == 400

    def test_patch_order_not_found_returns_404(self, auth_client):
        response = auth_client.patch(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        assert response.status_code == 404

    def test_patch_invalid_uuid_returns_400(self, auth_client):
        response = auth_client.patch(
            "/api/v1/orders/not-a-uuid/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        assert response.status_code == 400


# ===========================================================================
# POST — Cancel Action
# ===========================================================================


class TestCancelActionSuccess:
    def test_cancel_pending_order(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            {"notes": "Customer changed mind"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == OrderStatus.CANCELLED

    def test_cancel_confirmed_order(self, auth_client, created_order):
        order_id = created_order["id"]
        # First move to CONFIRMED
        auth_client.patch(
            f"/api/v1/orders/{order_id}/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        # Then cancel
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            {"notes": "Cancellation after confirmation"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == OrderStatus.CANCELLED

    def test_cancel_releases_stock(self, auth_client, created_order, product):
        """Cancelling should restore reserved stock."""
        order_id = created_order["id"]
        # After order creation, stock should be 100 - 5 = 95
        product.refresh_from_db()
        assert product.stock_quantity == 95

        auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            format="json",
        )

        product.refresh_from_db()
        assert product.stock_quantity == 100

    def test_cancel_without_notes(self, auth_client, created_order):
        order_id = created_order["id"]
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == OrderStatus.CANCELLED

    def test_cancel_records_history(self, auth_client, created_order):
        order_id = created_order["id"]
        auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            {"notes": "History test"},
            format="json",
        )
        response = auth_client.get(f"/api/v1/orders/{order_id}/")
        history = response.data["status_history"]
        statuses = [h["new_status"] for h in history]
        assert OrderStatus.CANCELLED in statuses


class TestCancelActionValidation:
    def test_cancel_shipped_order_returns_400(self, auth_client, created_order):
        """Cannot cancel an order that has been shipped."""
        order_id = created_order["id"]
        # Progress to SHIPPED
        for next_status in [
            OrderStatus.CONFIRMED,
            OrderStatus.SEPARATED,
            OrderStatus.SHIPPED,
        ]:
            auth_client.patch(
                f"/api/v1/orders/{order_id}/",
                {"status": next_status},
                format="json",
            )
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            format="json",
        )
        assert response.status_code == 400

    def test_cancel_delivered_order_returns_400(self, auth_client, created_order):
        """Cannot cancel a delivered order."""
        order_id = created_order["id"]
        # Progress to DELIVERED
        for next_status in [
            OrderStatus.CONFIRMED,
            OrderStatus.SEPARATED,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
        ]:
            auth_client.patch(
                f"/api/v1/orders/{order_id}/",
                {"status": next_status},
                format="json",
            )
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            format="json",
        )
        assert response.status_code == 400

    def test_cancel_already_cancelled_returns_400(self, auth_client, created_order):
        """Cannot cancel an already cancelled order."""
        order_id = created_order["id"]
        auth_client.post(f"/api/v1/orders/{order_id}/cancel/", format="json")
        response = auth_client.post(
            f"/api/v1/orders/{order_id}/cancel/",
            format="json",
        )
        assert response.status_code == 400

    def test_cancel_order_not_found_returns_404(self, auth_client):
        response = auth_client.post(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/cancel/",
            format="json",
        )
        assert response.status_code == 404

    def test_cancel_invalid_uuid_returns_400(self, auth_client):
        response = auth_client.post(
            "/api/v1/orders/not-a-uuid/cancel/",
            format="json",
        )
        assert response.status_code == 400


# ===========================================================================
# Authentication
# ===========================================================================


class TestUpdateCancelAuth:
    def test_patch_unauthenticated_returns_401(self, api_client):
        response = api_client.patch(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/",
            {"status": OrderStatus.CONFIRMED},
            format="json",
        )
        assert response.status_code == 401

    def test_cancel_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/cancel/",
            format="json",
        )
        assert response.status_code == 401
