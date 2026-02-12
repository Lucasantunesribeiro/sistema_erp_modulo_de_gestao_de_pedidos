"""Integration tests for Order idempotency.

Covers:
- Replay same idempotency key 3x returns same order (2xx).
- Different keys create distinct orders.
- Optional: same key with different payload either returns same order or rejects.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.models import Order
from modules.products.models import Product, ProductStatus

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

User = get_user_model()

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="idemuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Idempotency Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="idempotency@example.com",
        is_active=True,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="IDEMP-A",
        name="Idempotency Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="IDEMP-B",
        name="Idempotency Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
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
        "notes": "Idempotency test order",
    }


@pytest.fixture()
def alt_order_payload(customer, product_b):
    return {
        "customer_id": str(customer.id),
        "items": [{"product_id": str(product_b.id), "quantity": 3}],
        "notes": "Alternate payload",
    }


# ===========================================================================
# Replay same key
# ===========================================================================


class TestOrderIdempotencyReplay:
    def test_replay_same_key_returns_same_order(self, auth_client, order_payload):
        key = "replay-key-abc"
        responses = [
            auth_client.post(
                "/api/v1/orders/",
                order_payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=key,
            )
            for _ in range(3)
        ]
        for response in responses:
            assert response.status_code in {200, 201}

        assert Order.objects.count() == 1
        first = responses[0].data
        for response in responses[1:]:
            assert response.data["id"] == first["id"]
            assert response.data["order_number"] == first["order_number"]
            assert response.data["total_amount"] == first["total_amount"]
            assert response.data["items"] == first["items"]


# ===========================================================================
# Different keys
# ===========================================================================


class TestOrderIdempotencyDifferentKeys:
    def test_different_keys_create_two_orders(self, auth_client, order_payload):
        r1 = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-alpha",
        )
        r2 = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-beta",
        )

        assert r1.status_code in {200, 201}
        assert r2.status_code in {200, 201}
        assert r1.data["id"] != r2.data["id"]
        assert Order.objects.count() == 2


# ===========================================================================
# Payload mismatch (optional)
# ===========================================================================


class TestOrderIdempotencyPayloadMismatch:
    def test_same_key_with_different_payload(
        self, auth_client, order_payload, alt_order_payload
    ):
        key = "payload-key-xyz"
        r1 = auth_client.post(
            "/api/v1/orders/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        r2 = auth_client.post(
            "/api/v1/orders/",
            alt_order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        assert r1.status_code in {200, 201}
        assert r2.status_code in {200, 201, 409, 422}
        assert Order.objects.count() == 1

        if r2.status_code in {200, 201}:
            assert r2.data["id"] == r1.data["id"]
