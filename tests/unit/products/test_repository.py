"""Unit tests for ProductDjangoRepository.

Covers:
- CRUD operations (get_by_id, list, save, delete).
- Product-specific queries (get_by_sku, check_stock).
- Edge cases (invalid UUIDs, soft-deleted records).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.products.models import Product, ProductStatus
from modules.products.repositories.django_repository import ProductDjangoRepository
from modules.products.repositories.interfaces import IProductRepository

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(**overrides) -> Product:
    defaults = {
        "sku": "SKU-001",
        "name": "Widget",
        "price": Decimal("19.99"),
        "stock_quantity": 10,
    }
    defaults.update(overrides)
    product = Product(**defaults)
    product.save()
    return product


# ===========================================================================
# Instantiation
# ===========================================================================


class TestRepositoryInstantiation:
    def test_can_instantiate(self):
        repo = ProductDjangoRepository()
        assert repo is not None

    def test_is_instance_of_interface(self):
        repo = ProductDjangoRepository()
        assert isinstance(repo, IProductRepository)


# ===========================================================================
# get_by_id
# ===========================================================================


class TestGetById:
    def test_returns_product_when_found(self):
        product = _make_product()
        repo = ProductDjangoRepository()
        result = repo.get_by_id(str(product.id))
        assert result is not None
        assert result.id == product.id

    def test_returns_none_when_not_found(self):
        repo = ProductDjangoRepository()
        result = repo.get_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_returns_none_for_invalid_uuid(self):
        repo = ProductDjangoRepository()
        result = repo.get_by_id("not-a-uuid")
        assert result is None

    def test_returns_soft_deleted_product(self):
        product = _make_product()
        product.delete()
        repo = ProductDjangoRepository()
        result = repo.get_by_id(str(product.id))
        assert result is not None
        assert result.deleted_at is not None


# ===========================================================================
# list
# ===========================================================================


class TestList:
    def test_returns_all_products(self):
        _make_product(sku="SKU-A")
        _make_product(sku="SKU-B")
        repo = ProductDjangoRepository()
        results = repo.list()
        assert len(results) == 2

    def test_returns_empty_list_when_no_products(self):
        repo = ProductDjangoRepository()
        results = repo.list()
        assert results == []

    def test_filters_by_status(self):
        _make_product(sku="SKU-A", status=ProductStatus.ACTIVE)
        _make_product(sku="SKU-B", status=ProductStatus.INACTIVE)
        repo = ProductDjangoRepository()
        results = repo.list({"status": ProductStatus.ACTIVE})
        assert len(results) == 1
        assert results[0].sku == "SKU-A"

    def test_filters_by_name_icontains(self):
        _make_product(sku="SKU-A", name="Widget Pro")
        _make_product(sku="SKU-B", name="Gadget Basic")
        repo = ProductDjangoRepository()
        results = repo.list({"name__icontains": "widget"})
        assert len(results) == 1
        assert results[0].name == "Widget Pro"


# ===========================================================================
# save
# ===========================================================================


class TestSave:
    def test_creates_new_product(self):
        repo = ProductDjangoRepository()
        product = Product(
            sku="SKU-NEW",
            name="New Product",
            price=Decimal("9.99"),
            stock_quantity=5,
        )
        saved = repo.save(product)
        assert saved.id is not None
        assert Product.objects.filter(id=saved.id).exists()

    def test_updates_existing_product(self):
        product = _make_product()
        repo = ProductDjangoRepository()
        product.name = "Updated Name"
        repo.save(product)
        product.refresh_from_db()
        assert product.name == "Updated Name"

    def test_returns_same_entity(self):
        repo = ProductDjangoRepository()
        product = Product(
            sku="SKU-RET",
            name="Return Test",
            price=Decimal("5.00"),
        )
        saved = repo.save(product)
        assert saved is product


# ===========================================================================
# delete
# ===========================================================================


class TestDelete:
    def test_soft_deletes_existing_product(self):
        product = _make_product()
        repo = ProductDjangoRepository()
        result = repo.delete(str(product.id))
        assert result is True
        product.refresh_from_db()
        assert product.deleted_at is not None

    def test_returns_false_for_nonexistent(self):
        repo = ProductDjangoRepository()
        result = repo.delete("00000000-0000-0000-0000-000000000000")
        assert result is False

    def test_returns_false_for_invalid_uuid(self):
        repo = ProductDjangoRepository()
        result = repo.delete("not-a-uuid")
        assert result is False


# ===========================================================================
# get_by_sku
# ===========================================================================


class TestGetBySku:
    def test_returns_product_when_found(self):
        product = _make_product(sku="SKU-FIND")
        repo = ProductDjangoRepository()
        result = repo.get_by_sku("SKU-FIND")
        assert result is not None
        assert result.id == product.id

    def test_returns_none_when_not_found(self):
        repo = ProductDjangoRepository()
        result = repo.get_by_sku("NONEXISTENT")
        assert result is None

    def test_normalises_sku_on_lookup(self):
        _make_product(sku="SKU-CASE")
        repo = ProductDjangoRepository()
        result = repo.get_by_sku("  sku-case  ")
        assert result is not None
        assert result.sku == "SKU-CASE"


# ===========================================================================
# check_stock
# ===========================================================================


class TestCheckStock:
    def test_sufficient_stock_returns_true(self):
        product = _make_product(stock_quantity=10)
        repo = ProductDjangoRepository()
        assert repo.check_stock(str(product.id), 5) is True

    def test_exact_stock_returns_true(self):
        product = _make_product(stock_quantity=10)
        repo = ProductDjangoRepository()
        assert repo.check_stock(str(product.id), 10) is True

    def test_insufficient_stock_returns_false(self):
        product = _make_product(stock_quantity=3)
        repo = ProductDjangoRepository()
        assert repo.check_stock(str(product.id), 5) is False

    def test_nonexistent_product_returns_false(self):
        repo = ProductDjangoRepository()
        assert repo.check_stock("00000000-0000-0000-0000-000000000000", 1) is False
