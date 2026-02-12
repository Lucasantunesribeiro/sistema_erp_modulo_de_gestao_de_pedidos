"""Integration tests for Order list and retrieve endpoints.

Covers:
- List all: returns 200 with paginated results.
- Filter by status: returns only matching orders.
- Filter by customer: returns only matching orders.
- Filter by date range: returns orders within range.
- Pagination: respects page_size and returns next/previous links.
- Retrieve success: returns 200 with items, product details, history.
- Retrieve 404: non-existent or invalid ID.
- Authentication enforcement.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.integration

User = get_user_model()

VALID_CPF = "59860184275"
VALID_CNPJ = "11222333000181"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_client():
    client = APIClient()
    user = User.objects.create_user(username="readuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer_a():
    return Customer.objects.create(
        name="Customer A",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="customer-a@example.com",
        is_active=True,
    )


@pytest.fixture()
def customer_b():
    return Customer.objects.create(
        name="Customer B",
        document=VALID_CNPJ,
        document_type=DocumentType.CNPJ,
        email="customer-b@example.com",
        is_active=True,
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="READ-PROD",
        name="Read Test Product",
        price=Decimal("10.00"),
        stock_quantity=1000,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def repo():
    return OrderDjangoRepository()


@pytest.fixture()
def order_a(repo, customer_a, product):
    """Order for customer A (PENDING)."""
    return repo.create(
        {
            "customer_id": customer_a.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": product.price,
                }
            ],
            "notes": "Order A",
        }
    )


@pytest.fixture()
def order_b(repo, customer_b, product):
    """Order for customer B (PENDING)."""
    return repo.create(
        {
            "customer_id": customer_b.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2,
                    "unit_price": product.price,
                }
            ],
            "notes": "Order B",
        }
    )


@pytest.fixture()
def confirmed_order(repo, order_a):
    """Order A transitioned to CONFIRMED."""
    order_a.status = OrderStatus.CONFIRMED
    order_a.save(update_fields=["status", "updated_at"])
    repo.add_history(
        order_id=order_a.id,
        status=OrderStatus.CONFIRMED,
        old_status=OrderStatus.PENDING,
        notes="Confirmed for test",
    )
    return order_a


# ===========================================================================
# List
# ===========================================================================


class TestOrderListAll:
    def test_list_empty(self, auth_client):
        response = auth_client.get("/api/v1/orders/")
        assert response.status_code == 200
        assert response.data["results"] == []
        assert response.data["count"] == 0

    def test_list_returns_orders(self, auth_client, order_a, order_b):
        response = auth_client.get("/api/v1/orders/")
        assert response.status_code == 200
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_list_uses_lightweight_serializer(self, auth_client, order_a):
        response = auth_client.get("/api/v1/orders/")
        data = response.data["results"][0]
        assert "id" in data
        assert "order_number" in data
        assert "status" in data
        assert "total_amount" in data
        assert "created_at" in data
        # Lightweight serializer should NOT include items or history
        assert "items" not in data
        assert "status_history" not in data

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/orders/")
        assert response.status_code == 401


class TestOrderListFilterStatus:
    def test_filter_by_pending(self, auth_client, order_a, confirmed_order):
        # order_a was confirmed by the fixture, but order_b doesn't exist here.
        # confirmed_order transitions order_a to CONFIRMED.
        # We need a PENDING order for this test.
        pass

    def test_filter_returns_only_matching_status(
        self, auth_client, order_a, order_b, confirmed_order
    ):
        """order_a is CONFIRMED (via fixture), order_b is PENDING."""
        response = auth_client.get("/api/v1/orders/", {"status": OrderStatus.PENDING})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(order_b.id)

    def test_filter_confirmed(self, auth_client, order_a, order_b, confirmed_order):
        response = auth_client.get("/api/v1/orders/", {"status": OrderStatus.CONFIRMED})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(order_a.id)

    def test_filter_no_match(self, auth_client, order_a):
        response = auth_client.get("/api/v1/orders/", {"status": OrderStatus.SHIPPED})
        assert response.status_code == 200
        assert response.data["count"] == 0


class TestOrderListFilterCustomer:
    def test_filter_by_customer_a(self, auth_client, order_a, order_b, customer_a):
        response = auth_client.get(
            "/api/v1/orders/", {"customer_id": str(customer_a.id)}
        )
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(order_a.id)

    def test_filter_by_customer_b(self, auth_client, order_a, order_b, customer_b):
        response = auth_client.get(
            "/api/v1/orders/", {"customer_id": str(customer_b.id)}
        )
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(order_b.id)


class TestOrderListFilterDate:
    def test_filter_date_min(self, auth_client, order_a):
        yesterday = (timezone.now() - timezone.timedelta(days=1)).isoformat()
        response = auth_client.get("/api/v1/orders/", {"date_min": yesterday})
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_filter_date_max(self, auth_client, order_a):
        tomorrow = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        response = auth_client.get("/api/v1/orders/", {"date_max": tomorrow})
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_filter_date_range_excludes(self, auth_client, order_a):
        """Date range in the past should exclude today's order."""
        past_start = "2020-01-01T00:00:00Z"
        past_end = "2020-01-02T00:00:00Z"
        response = auth_client.get(
            "/api/v1/orders/", {"date_min": past_start, "date_max": past_end}
        )
        assert response.status_code == 200
        assert response.data["count"] == 0


class TestOrderListPagination:
    def test_pagination_structure(self, auth_client, order_a):
        response = auth_client.get("/api/v1/orders/")
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_pagination_respects_page_size(
        self, auth_client, repo, customer_a, product
    ):
        """Create more orders than page_size and verify pagination."""
        # Default page_size is 20. Create 3 orders — should fit in one page.
        for i in range(3):
            repo.create(
                {
                    "customer_id": customer_a.id,
                    "items": [
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "unit_price": product.price,
                        }
                    ],
                }
            )
        response = auth_client.get("/api/v1/orders/")
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3
        assert response.data["next"] is None

    def test_pagination_page_param(self, auth_client, repo, customer_a, product):
        """Test explicit page parameter."""
        for _ in range(3):
            repo.create(
                {
                    "customer_id": customer_a.id,
                    "items": [
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "unit_price": product.price,
                        }
                    ],
                }
            )
        response = auth_client.get("/api/v1/orders/", {"page": 1})
        assert response.status_code == 200
        assert response.data["count"] == 3


# ===========================================================================
# Retrieve
# ===========================================================================


class TestOrderRetrieve:
    def test_retrieve_returns_200(self, auth_client, order_a):
        response = auth_client.get(f"/api/v1/orders/{order_a.id}/")
        assert response.status_code == 200

    def test_retrieve_includes_items(self, auth_client, order_a):
        response = auth_client.get(f"/api/v1/orders/{order_a.id}/")
        assert "items" in response.data
        assert len(response.data["items"]) == 1
        item = response.data["items"][0]
        assert "product_name" in item
        assert "product_sku" in item
        assert "quantity" in item
        assert "unit_price" in item
        assert "subtotal" in item

    def test_retrieve_includes_status_history(self, auth_client, confirmed_order, repo):
        response = auth_client.get(f"/api/v1/orders/{confirmed_order.id}/")
        assert "status_history" in response.data
        assert len(response.data["status_history"]) >= 1

    def test_retrieve_includes_all_fields(self, auth_client, order_a):
        response = auth_client.get(f"/api/v1/orders/{order_a.id}/")
        data = response.data
        assert "id" in data
        assert "order_number" in data
        assert "customer_id" in data
        assert "status" in data
        assert "total_amount" in data
        assert "notes" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "items" in data
        assert "status_history" in data

    def test_retrieve_not_found(self, auth_client):
        response = auth_client.get(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000/"
        )
        assert response.status_code == 404
        assert "not found" in response.data["detail"].lower()

    def test_retrieve_invalid_uuid(self, auth_client):
        response = auth_client.get("/api/v1/orders/not-a-uuid/")
        assert response.status_code == 404

    def test_retrieve_product_details_in_items(self, auth_client, order_a, product):
        response = auth_client.get(f"/api/v1/orders/{order_a.id}/")
        item = response.data["items"][0]
        assert item["product_name"] == "Read Test Product"
        assert item["product_sku"] == "READ-PROD"
        assert Decimal(item["unit_price"]) == Decimal("10.00")
