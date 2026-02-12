"""Unit tests for Product DRF serializers.

Covers:
- Field presence and read-only constraints.
- Serialization of a Product instance.
- Deserialization and uniqueness validation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from modules.products.models import Product
from modules.products.serializers import ProductSerializer

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(**overrides) -> Product:
    defaults = {
        "sku": f"SKU-{uuid.uuid4().hex[:6].upper()}",
        "name": "Widget",
        "price": Decimal("19.99"),
        "stock_quantity": 10,
    }
    defaults.update(overrides)
    product = Product(**defaults)
    product.save()
    return product


# ===========================================================================
# Field presence
# ===========================================================================


class TestSerializerFields:
    def test_expected_fields(self):
        serializer = ProductSerializer()
        expected = {
            "id",
            "sku",
            "name",
            "description",
            "price",
            "stock_quantity",
            "status",
            "created_at",
            "updated_at",
        }
        assert set(serializer.fields.keys()) == expected

    def test_read_only_fields(self):
        serializer = ProductSerializer()
        for field_name in ("id", "created_at", "updated_at"):
            assert serializer.fields[field_name].read_only is True


# ===========================================================================
# Serialization (Model -> JSON)
# ===========================================================================


class TestSerialization:
    def test_serializes_product(self):
        product = _make_product()
        data = ProductSerializer(product).data
        assert data["id"] == str(product.id)
        assert data["sku"] == product.sku
        assert data["name"] == "Widget"
        assert Decimal(data["price"]) == Decimal("19.99")
        assert data["stock_quantity"] == 10
        assert data["status"] == "active"

    def test_serializes_optional_fields(self):
        product = _make_product(description="A fine widget")
        data = ProductSerializer(product).data
        assert data["description"] == "A fine widget"


# ===========================================================================
# Deserialization (JSON -> validated data)
# ===========================================================================


class TestDeserialization:
    def test_valid_input(self):
        payload = {
            "sku": "SKU-NEW",
            "name": "New Widget",
            "price": "29.99",
            "stock_quantity": 5,
        }
        serializer = ProductSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "New Widget"

    def test_missing_required_field(self):
        payload = {"name": "No SKU"}
        serializer = ProductSerializer(data=payload)
        assert not serializer.is_valid()
        assert "sku" in serializer.errors

    def test_duplicate_sku_rejected(self):
        _make_product(sku="SKU-DUP")
        payload = {
            "sku": "SKU-DUP",
            "name": "Duplicate",
            "price": "10.00",
        }
        serializer = ProductSerializer(data=payload)
        assert not serializer.is_valid()
        assert "sku" in serializer.errors
