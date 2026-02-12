"""Unit tests for Order DRF Serializers.

Covers:
- CreateOrderItemSerializer: field validation.
- CreateOrderSerializer: nested items validation.
- OrderItemSerializer: read-only output fields.
- OrderSerializer: nested read output.
- OrderListSerializer: lightweight list output.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.serializers import (
    CreateOrderItemSerializer,
    CreateOrderSerializer,
    OrderItemSerializer,
    OrderListSerializer,
    OrderSerializer,
)
from modules.products.models import Product

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Serializer Customer",
        document="59860184275",
        document_type=DocumentType.CPF,
        email="ser-test@example.com",
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="SER-PROD",
        name="Serializer Product",
        price=Decimal("15.00"),
        stock_quantity=50,
    )


@pytest.fixture()
def order(customer, product):
    repo = OrderDjangoRepository()
    return repo.create(
        {
            "customer_id": customer.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2,
                    "unit_price": product.price,
                },
            ],
            "notes": "Test order",
        }
    )


# ===========================================================================
# CreateOrderItemSerializer
# ===========================================================================


class TestCreateOrderItemSerializer:
    def test_valid_data(self):
        data = {"product_id": str(uuid4()), "quantity": 3}
        serializer = CreateOrderItemSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_product_id(self):
        data = {"quantity": 1}
        serializer = CreateOrderItemSerializer(data=data)
        assert not serializer.is_valid()
        assert "product_id" in serializer.errors

    def test_missing_quantity(self):
        data = {"product_id": str(uuid4())}
        serializer = CreateOrderItemSerializer(data=data)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors

    def test_zero_quantity_invalid(self):
        data = {"product_id": str(uuid4()), "quantity": 0}
        serializer = CreateOrderItemSerializer(data=data)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors

    def test_negative_quantity_invalid(self):
        data = {"product_id": str(uuid4()), "quantity": -1}
        serializer = CreateOrderItemSerializer(data=data)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors


# ===========================================================================
# CreateOrderSerializer
# ===========================================================================


class TestCreateOrderSerializer:
    def test_valid_data(self):
        data = {
            "customer_id": str(uuid4()),
            "items": [{"product_id": str(uuid4()), "quantity": 2}],
        }
        serializer = CreateOrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_empty_items_invalid(self):
        data = {"customer_id": str(uuid4()), "items": []}
        serializer = CreateOrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "items" in serializer.errors

    def test_missing_items_invalid(self):
        data = {"customer_id": str(uuid4())}
        serializer = CreateOrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "items" in serializer.errors

    def test_missing_customer_id_invalid(self):
        data = {"items": [{"product_id": str(uuid4()), "quantity": 1}]}
        serializer = CreateOrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "customer_id" in serializer.errors

    def test_notes_optional(self):
        data = {
            "customer_id": str(uuid4()),
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
        }
        serializer = CreateOrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["notes"] == ""

    def test_notes_provided(self):
        data = {
            "customer_id": str(uuid4()),
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "notes": "Please rush",
        }
        serializer = CreateOrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["notes"] == "Please rush"


# ===========================================================================
# OrderItemSerializer (read)
# ===========================================================================


class TestOrderItemSerializer:
    def test_serializes_item_with_product_info(self, order):
        from modules.orders.models import OrderItem

        item = OrderItem.objects.select_related("product").filter(order=order).first()
        serializer = OrderItemSerializer(item)
        data = serializer.data

        assert "product_name" in data
        assert "product_sku" in data
        assert data["quantity"] == 2
        assert Decimal(data["unit_price"]) == Decimal("15.00")
        assert Decimal(data["subtotal"]) == Decimal("30.00")


# ===========================================================================
# OrderSerializer (read with nested)
# ===========================================================================


class TestOrderSerializer:
    def test_serializes_order_with_items_and_history(self, order):
        repo = OrderDjangoRepository()
        fetched = repo.get_by_id(str(order.id))
        serializer = OrderSerializer(fetched)
        data = serializer.data

        assert data["order_number"].startswith("ORD-")
        assert data["status"] == "PENDING"
        assert len(data["items"]) == 1
        assert "status_history" in data


# ===========================================================================
# OrderListSerializer (lightweight)
# ===========================================================================


class TestOrderListSerializer:
    def test_serializes_lightweight(self, order):
        serializer = OrderListSerializer(order)
        data = serializer.data

        assert "order_number" in data
        assert "status" in data
        assert "items" not in data
        assert "status_history" not in data
