"""Unit tests for the Product model.

Covers:
- Valid creation with all fields.
- SKU uppercase normalisation on save and full_clean.
- SKU uniqueness constraint.
- Price > 0 validation (application + DB constraint).
- Stock quantity >= 0 (PositiveIntegerField).
- Soft delete lifecycle (inherited from SoftDeleteModel).
- __str__ representation.
- INFO log on product creation.
- Status default and update.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(**overrides) -> Product:
    """Build and full_clean a Product, returning the unsaved instance."""
    defaults = {
        "sku": f"TST-{uuid.uuid4().hex[:6].upper()}",
        "name": "Test Product",
        "price": Decimal("29.90"),
        "stock_quantity": 100,
    }
    defaults.update(overrides)
    product = Product(**defaults)
    product.full_clean()
    return product


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestProductCreation:
    """Happy-path creation."""

    def test_create_product_with_valid_data(self):
        p = Product.objects.create(
            sku="PROD-001",
            name="Widget",
            price=Decimal("19.99"),
            stock_quantity=50,
        )
        p.refresh_from_db()
        assert p.sku == "PROD-001"
        assert p.name == "Widget"
        assert p.price == Decimal("19.99")
        assert p.stock_quantity == 50
        assert p.status == ProductStatus.ACTIVE
        assert p.is_deleted is False

    def test_id_is_uuid7(self):
        p = Product.objects.create(
            sku="UUID-CHECK",
            name="UUID Product",
            price=Decimal("10.00"),
        )
        assert isinstance(p.id, uuid.UUID)
        assert p.id.version == 7

    def test_timestamps_set_on_create(self):
        p = Product.objects.create(
            sku="TS-CHECK",
            name="Timestamp Product",
            price=Decimal("5.00"),
        )
        assert p.created_at is not None
        assert p.updated_at is not None

    def test_default_stock_is_zero(self):
        p = Product.objects.create(
            sku="DEFAULT-STOCK",
            name="Default Stock",
            price=Decimal("10.00"),
        )
        assert p.stock_quantity == 0

    def test_description_is_optional(self):
        p = Product.objects.create(
            sku="NO-DESC",
            name="No Description",
            price=Decimal("10.00"),
        )
        assert p.description == ""


# ---------------------------------------------------------------------------
# SKU Normalisation
# ---------------------------------------------------------------------------


class TestSkuNormalisation:
    """SKU is uppercased and stripped on save and full_clean."""

    def test_sku_uppercased_on_save(self):
        p = Product.objects.create(
            sku="lower-sku",
            name="Lowercase SKU",
            price=Decimal("10.00"),
        )
        p.refresh_from_db()
        assert p.sku == "LOWER-SKU"

    def test_sku_stripped_on_save(self):
        p = Product.objects.create(
            sku="  spaced  ",
            name="Spaced SKU",
            price=Decimal("10.00"),
        )
        p.refresh_from_db()
        assert p.sku == "SPACED"

    def test_sku_uppercased_via_full_clean(self):
        p = _make_product(sku="via-clean")
        assert p.sku == "VIA-CLEAN"


# ---------------------------------------------------------------------------
# SKU Uniqueness
# ---------------------------------------------------------------------------


class TestSkuUniqueness:
    """RN-PRO-001: SKU must be unique."""

    def test_duplicate_sku_raises(self):
        Product.objects.create(
            sku="UNIQUE-SKU",
            name="First",
            price=Decimal("10.00"),
        )
        with pytest.raises(IntegrityError):
            Product.objects.create(
                sku="UNIQUE-SKU",
                name="Second",
                price=Decimal("20.00"),
            )


# ---------------------------------------------------------------------------
# Price Validation
# ---------------------------------------------------------------------------


class TestPriceValidation:
    """RN-PRO-003: Price must be greater than zero."""

    def test_zero_price_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Price must be greater than zero"):
            _make_product(price=Decimal("0.00"))

    def test_negative_price_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Price must be greater than zero"):
            _make_product(price=Decimal("-5.00"))

    def test_minimum_valid_price(self):
        p = _make_product(price=Decimal("0.01"))
        assert p.price == Decimal("0.01")


# ---------------------------------------------------------------------------
# Stock Validation
# ---------------------------------------------------------------------------


class TestStockValidation:
    """RN-PRO-004: Stock quantity cannot be negative."""

    def test_negative_stock_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Stock quantity cannot be negative"):
            _make_product(stock_quantity=-1)

    def test_zero_stock_is_valid(self):
        p = _make_product(stock_quantity=0)
        assert p.stock_quantity == 0


# ---------------------------------------------------------------------------
# Soft Delete
# ---------------------------------------------------------------------------


class TestProductSoftDelete:
    """RN-PRO-005: soft delete via inherited SoftDeleteModel."""

    def test_delete_sets_deleted_at(self):
        p = Product.objects.create(
            sku="DEL-001",
            name="Delete Me",
            price=Decimal("10.00"),
        )
        p.delete()
        p.refresh_from_db()
        assert p.is_deleted is True
        assert p.deleted_at is not None

    def test_soft_deleted_excluded_from_alive(self):
        p = Product.objects.create(
            sku="ALIVE-001",
            name="Alive Check",
            price=Decimal("10.00"),
        )
        p.delete()
        assert not Product.objects.alive().filter(pk=p.pk).exists()

    def test_soft_deleted_still_in_objects_all(self):
        p = Product.objects.create(
            sku="ALL-001",
            name="All Check",
            price=Decimal("10.00"),
        )
        p.delete()
        assert Product.objects.filter(pk=p.pk).exists()

    def test_restore_after_soft_delete(self):
        p = Product.objects.create(
            sku="RESTORE-001",
            name="Restore Me",
            price=Decimal("10.00"),
        )
        p.delete()
        p.restore()
        p.refresh_from_db()
        assert p.is_deleted is False

    def test_hard_delete_removes_from_db(self):
        p = Product.objects.create(
            sku="HARD-DEL-001",
            name="Hard Delete",
            price=Decimal("10.00"),
        )
        pk = p.pk
        p.hard_delete()
        assert not Product.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class TestProductDisplay:
    """__str__ returns 'SKU - Name'."""

    def test_str_representation(self):
        p = _make_product(sku="DISP-001", name="Display Product")
        assert str(p) == "DISP-001 - Display Product"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestProductStatus:
    """Status defaults to 'active' and can be changed."""

    def test_default_status_is_active(self):
        p = Product.objects.create(
            sku="STATUS-001",
            name="Active Product",
            price=Decimal("10.00"),
        )
        assert p.status == ProductStatus.ACTIVE

    def test_can_set_inactive(self):
        p = Product.objects.create(
            sku="STATUS-002",
            name="Inactive Product",
            price=Decimal("10.00"),
        )
        p.status = ProductStatus.INACTIVE
        p.save(update_fields=["status"])
        p.refresh_from_db()
        assert p.status == ProductStatus.INACTIVE


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestProductLogging:
    """Product creation emits an INFO log."""

    def test_creation_logs_info(self, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="modules.products.models"):
            Product.objects.create(
                sku="LOG-001",
                name="Logged Product",
                price=Decimal("10.00"),
            )
        assert len(caplog.records) >= 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert "product_created" in record.getMessage()

    def test_update_does_not_log_creation(self, caplog):
        import logging

        p = Product.objects.create(
            sku="LOG-002",
            name="No Re-log",
            price=Decimal("10.00"),
        )
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="modules.products.models"):
            p.name = "Updated Name"
            p.save(update_fields=["name"])
        creation_logs = [
            r for r in caplog.records if "product_created" in r.getMessage()
        ]
        assert len(creation_logs) == 0
