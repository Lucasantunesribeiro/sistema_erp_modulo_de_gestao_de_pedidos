"""Performance regression tests — constant query count (N+1 prevention).

Verifies that list and retrieve endpoints execute a bounded number of
SQL queries regardless of the number of records, proving that
``select_related`` / ``prefetch_related`` are correctly applied.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.models import Order, OrderItem
from modules.products.models import Product, ProductStatus

User = get_user_model()

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    client = APIClient()
    user = User.objects.create_user(username="perfuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Perf Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="perf@test.com",
        is_active=True,
    )


@pytest.fixture()
def products():
    return [
        Product.objects.create(
            sku=f"PERF-{i:03d}",
            name=f"Product {i}",
            price=Decimal("10.00"),
            stock_quantity=1000,
            status=ProductStatus.ACTIVE,
        )
        for i in range(5)
    ]


@pytest.fixture()
def orders_with_items(customer, products):
    """Create multiple orders each with multiple items."""
    orders = []
    for i in range(10):
        order = Order(customer=customer, status=OrderStatus.PENDING)
        order.save()
        for product in products[:3]:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                unit_price=product.price,
                subtotal=product.price,
            )
        orders.append(order)
    return orders


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrderListQueryCount:
    """Verify the order list endpoint runs a constant number of queries."""

    def test_list_query_count_is_constant(
        self, auth_client, orders_with_items, django_assert_max_num_queries
    ):
        """GET /api/v1/orders/ should not increase queries with more records.

        Expected queries (bounded):
        1. Session/auth lookup
        2. COUNT for pagination
        3. SELECT orders with JOIN customer (select_related)
        Total: ~3 queries (no prefetch needed for list serializer).
        """
        with django_assert_max_num_queries(5):
            response = auth_client.get("/api/v1/orders/")

        assert response.status_code == 200
        assert response.data["count"] == 10


@pytest.mark.django_db
class TestOrderRetrieveQueryCount:
    """Verify the order retrieve endpoint runs a constant number of queries."""

    def test_retrieve_query_count_is_constant(
        self, auth_client, orders_with_items, django_assert_max_num_queries
    ):
        """GET /api/v1/orders/{id}/ should use bounded queries via prefetch.

        Expected queries (bounded):
        1. Session/auth lookup
        2. SELECT order with JOIN customer (select_related)
        3. SELECT items with JOIN product (prefetch_related items__product)
        4. SELECT status_history (prefetch_related)
        Total: ~4 queries regardless of item count.
        """
        order = orders_with_items[0]

        with django_assert_max_num_queries(6):
            response = auth_client.get(f"/api/v1/orders/{order.id}/")

        assert response.status_code == 200
        assert len(response.data["items"]) == 3
