"""Integration test for order atomicity on partial stock failures.

Ensures stock reservation is all-or-nothing when any item lacks stock.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.models import Order
from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.integration

User = get_user_model()

VALID_CPF = "59860184275"


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="atomicuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Atomicity Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="atomicity@example.com",
        is_active=True,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="ATOMIC-A",
        name="Atomic Product A",
        price=Decimal("10.00"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="ATOMIC-B",
        name="Atomic Product B",
        price=Decimal("20.00"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_c():
    return Product.objects.create(
        sku="ATOMIC-C",
        name="Atomic Product C",
        price=Decimal("5.00"),
        stock_quantity=0,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def order_payload(customer, product_a, product_b, product_c):
    return {
        "customer_id": str(customer.id),
        "items": [
            {"product_id": str(product_a.id), "quantity": 1},
            {"product_id": str(product_b.id), "quantity": 1},
            {"product_id": str(product_c.id), "quantity": 1},
        ],
        "notes": "Atomicity test order",
    }


class TestOrderAtomicity:
    def test_atomicity_rolls_back_on_partial_stock_failure(
        self, auth_client, order_payload, product_a, product_b, product_c
    ):
        order_count_before = Order.objects.count()
        stock_a_before = product_a.stock_quantity
        stock_b_before = product_b.stock_quantity
        stock_c_before = product_c.stock_quantity

        response = auth_client.post("/api/v1/orders/", order_payload, format="json")

        assert response.status_code == 409
        assert Order.objects.count() == order_count_before

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        product_c.refresh_from_db()

        assert product_a.stock_quantity == stock_a_before
        assert product_b.stock_quantity == stock_b_before
        assert product_c.stock_quantity == stock_c_before
