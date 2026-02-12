"""Integration tests for Order creation endpoint.

Covers:
- Success 201: create a valid order with items.
- Validation 400: invalid payloads (missing items, zero quantity).
- Business 404/400/422: customer not found, inactive, insufficient stock.
- Idempotency: duplicate requests with same key return same order.
- Stock deduction: products stock decremented on creation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.models import Order
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
    user = User.objects.create_user(username="createuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Create Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="create-test@example.com",
        is_active=True,
    )


@pytest.fixture()
def inactive_customer():
    return Customer.objects.create(
        name="Inactive Customer",
        document="11222333000181",
        document_type=DocumentType.CNPJ,
        email="inactive-create@example.com",
        is_active=False,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="CREATE-A",
        name="Create Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="CREATE-B",
        name="Create Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def inactive_product():
    return Product.objects.create(
        sku="CREATE-INACTIVE",
        name="Inactive Create Product",
        price=Decimal("5.00"),
        stock_quantity=10,
        status=ProductStatus.INACTIVE,
    )


@pytest.fixture()
def low_stock_product():
    return Product.objects.create(
        sku="CREATE-LOW",
        name="Low Stock Create Product",
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
        "notes": "Create API test order",
    }


# ===========================================================================
# Success (201)
# ===========================================================================


class TestOrderCreateSuccess:
    def test_create_returns_201(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")
        assert response.status_code == 201

    def test_create_returns_order_data(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")
        data = response.data
        assert data["status"] == OrderStatus.PENDING
        assert data["order_number"].startswith("ORD-")
        assert len(data["items"]) == 2
        assert data["notes"] == "Create API test order"

    def test_create_calculates_total(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")
        # 2 * 10.00 + 1 * 25.50 = 45.50
        assert Decimal(response.data["total_amount"]) == Decimal("45.50")

    def test_create_deducts_stock(
        self, auth_client, order_payload, product_a, product_b
    ):
        auth_client.post("/api/v1/orders/", order_payload, format="json")

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 98  # 100 - 2
        assert product_b.stock_quantity == 49  # 50 - 1

    def test_create_records_status_history(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")
        assert len(response.data["status_history"]) == 1
        assert response.data["status_history"][0]["new_status"] == OrderStatus.PENDING

    def test_create_includes_item_product_details(self, auth_client, order_payload):
        response = auth_client.post("/api/v1/orders/", order_payload, format="json")
        items = response.data["items"]
        product_names = {item["product_name"] for item in items}
        assert "Create Product A" in product_names
        assert "Create Product B" in product_names


# ===========================================================================
# Validation (400)
# ===========================================================================


class TestOrderCreateValidation:
    def test_missing_customer_id_returns_400(self, auth_client, product_a):
        payload = {
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_empty_items_returns_400(self, auth_client, customer):
        payload = {
            "customer_id": str(customer.id),
            "items": [],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_missing_items_returns_400(self, auth_client, customer):
        payload = {
            "customer_id": str(customer.id),
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_zero_quantity_returns_400(self, auth_client, customer, product_a):
        payload = {
            "customer_id": str(customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": 0}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_negative_quantity_returns_400(self, auth_client, customer, product_a):
        payload = {
            "customer_id": str(customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": -1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_invalid_customer_uuid_returns_400(self, auth_client, product_a):
        payload = {
            "customer_id": "not-a-uuid",
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400

    def test_unauthenticated_returns_401(self, api_client, order_payload):
        response = api_client.post("/api/v1/orders/", order_payload, format="json")
        assert response.status_code == 401


# ===========================================================================
# Business Errors (404 / 400 / 422)
# ===========================================================================


class TestOrderCreateBusinessErrors:
    def test_customer_not_found_returns_404(self, auth_client, product_a):
        payload = {
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 404
        assert "Customer not found" in response.data["detail"]

    def test_inactive_customer_returns_400(
        self, auth_client, inactive_customer, product_a
    ):
        payload = {
            "customer_id": str(inactive_customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 400
        assert "inactive" in response.data["detail"].lower()

    def test_product_not_found_returns_404(self, auth_client, customer):
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
        assert "not found" in response.data["detail"].lower()

    def test_inactive_product_returns_400(
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
        assert "inactive" in response.data["detail"].lower()

    def test_insufficient_stock_returns_422(
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
        assert "available" in response.data["detail"].lower()


# ===========================================================================
# Idempotency
# ===========================================================================


class TestOrderCreateIdempotency:
    def test_idempotency_key_stored_on_order(self, auth_client, order_payload):
        response = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="test-key-123",
        )
        assert response.status_code == 201
        order = Order.objects.get(id=response.data["id"])
        assert order.idempotency_key == "test-key-123"

    def test_duplicate_key_returns_same_order(self, auth_client, order_payload):
        """Two requests with the same key must return the same order."""
        r1 = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="dedup-key-abc",
        )
        assert r1.status_code == 201
        order_id_1 = r1.data["id"]

        r2 = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="dedup-key-abc",
        )
        order_id_2 = r2.data["id"]

        assert order_id_1 == order_id_2

    def test_duplicate_key_does_not_deduct_stock_twice(
        self, auth_client, order_payload, product_a, product_b
    ):
        """Idempotent retry must not deduct stock again."""
        auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="stock-key-xyz",
        )
        auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="stock-key-xyz",
        )

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        # Stock should be deducted only once
        assert product_a.stock_quantity == 98  # 100 - 2
        assert product_b.stock_quantity == 49  # 50 - 1

    def test_duplicate_key_creates_only_one_order(self, auth_client, order_payload):
        """Only one order should exist in the database."""
        auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="one-order-key",
        )
        auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="one-order-key",
        )

        assert Order.objects.count() == 1

    def test_different_keys_create_separate_orders(
        self, auth_client, customer, product_a
    ):
        """Different keys must create different orders."""
        payload = {
            "customer_id": str(customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        r1 = auth_client.post(
            "/api/v1/orders/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-alpha",
        )
        r2 = auth_client.post(
            "/api/v1/orders/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-beta",
        )

        assert r1.data["id"] != r2.data["id"]
        assert Order.objects.count() == 2

    def test_no_key_creates_new_order_each_time(self, auth_client, customer, product_a):
        """Without idempotency key, each request creates a new order."""
        payload = {
            "customer_id": str(customer.id),
            "items": [{"product_id": str(product_a.id), "quantity": 1}],
        }
        r1 = auth_client.post("/api/v1/orders/", payload, format="json")
        r2 = auth_client.post("/api/v1/orders/", payload, format="json")

        assert r1.data["id"] != r2.data["id"]
        assert Order.objects.count() == 2
