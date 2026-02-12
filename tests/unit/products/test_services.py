"""Unit tests for ProductService.

Covers:
- create_product: happy path, duplicate SKU (RN-PRO-001).
- update_product: happy path, not found, partial update.
- get_product: happy path, not found.
- list_products: delegation to repository.
- delete_product: happy path, not found.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.products.dtos import CreateProductDTO, UpdateProductDTO
from modules.products.exceptions import ProductAlreadyExists, ProductNotFound
from modules.products.models import Product
from modules.products.services import ProductService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo():
    return MagicMock()


@pytest.fixture()
def service(mock_repo):
    return ProductService(repository=mock_repo)


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
# create_product
# ===========================================================================


class TestCreateProduct:
    def test_success(self, service, mock_repo):
        mock_repo.get_by_sku.return_value = None
        mock_repo.save.side_effect = lambda p: p

        dto = CreateProductDTO(
            sku="SKU-001",
            name="Widget",
            price=Decimal("19.99"),
        )
        product = service.create_product(dto)

        assert product.name == "Widget"
        assert product.sku == "SKU-001"
        assert product.price == Decimal("19.99")
        mock_repo.save.assert_called_once()

    def test_duplicate_sku_raises(self, service, mock_repo):
        mock_repo.get_by_sku.return_value = _make_product()

        dto = CreateProductDTO(
            sku="SKU-001",
            name="Duplicate",
            price=Decimal("10.00"),
        )
        with pytest.raises(ProductAlreadyExists, match="SKU"):
            service.create_product(dto)

        mock_repo.save.assert_not_called()

    def test_sets_optional_fields(self, service, mock_repo):
        mock_repo.get_by_sku.return_value = None
        mock_repo.save.side_effect = lambda p: p

        dto = CreateProductDTO(
            sku="SKU-002",
            name="Gadget",
            price=Decimal("29.99"),
            description="A fine gadget",
            stock_quantity=50,
        )
        product = service.create_product(dto)

        assert product.description == "A fine gadget"
        assert product.stock_quantity == 50


# ===========================================================================
# update_product
# ===========================================================================


class TestUpdateProduct:
    def test_success(self, service, mock_repo):
        existing = _make_product()
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda p: p

        dto = UpdateProductDTO(name="Updated Widget")
        product = service.update_product(str(existing.id), dto)

        assert product.name == "Updated Widget"
        mock_repo.save.assert_called_once()

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        dto = UpdateProductDTO(name="Ghost")
        with pytest.raises(ProductNotFound):
            service.update_product("non-existent-id", dto)

    def test_partial_update_preserves_other_fields(self, service, mock_repo):
        existing = _make_product(description="Original desc")
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda p: p

        dto = UpdateProductDTO(price=Decimal("39.99"))
        product = service.update_product(str(existing.id), dto)

        assert product.price == Decimal("39.99")
        assert product.description == "Original desc"
        assert product.name == "Widget"

    def test_update_status(self, service, mock_repo):
        existing = _make_product()
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda p: p

        dto = UpdateProductDTO(status="inactive")
        product = service.update_product(str(existing.id), dto)

        assert product.status == "inactive"

    def test_update_stock_quantity(self, service, mock_repo):
        existing = _make_product(stock_quantity=10)
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda p: p

        dto = UpdateProductDTO(stock_quantity=25)
        product = service.update_product(str(existing.id), dto)

        assert product.stock_quantity == 25


# ===========================================================================
# get_product
# ===========================================================================


class TestGetProduct:
    def test_success(self, service, mock_repo):
        existing = _make_product()
        mock_repo.get_by_id.return_value = existing

        product = service.get_product(str(existing.id))

        assert product.id == existing.id

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        with pytest.raises(ProductNotFound):
            service.get_product("non-existent-id")


# ===========================================================================
# list_products
# ===========================================================================


class TestListProducts:
    def test_delegates_to_repo(self, service, mock_repo):
        products = [_make_product(sku="A"), _make_product(sku="B")]
        mock_repo.list.return_value = products

        result = service.list_products()

        assert len(result) == 2
        mock_repo.list.assert_called_once_with(None)

    def test_passes_filters_to_repo(self, service, mock_repo):
        mock_repo.list.return_value = []
        filters = {"status": "active"}

        service.list_products(filters)

        mock_repo.list.assert_called_once_with(filters)


# ===========================================================================
# delete_product
# ===========================================================================


class TestDeleteProduct:
    def test_success(self, service, mock_repo):
        existing = _make_product()
        mock_repo.get_by_id.return_value = existing
        mock_repo.delete.return_value = True

        service.delete_product(str(existing.id))

        mock_repo.delete.assert_called_once_with(str(existing.id))

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        with pytest.raises(ProductNotFound):
            service.delete_product("non-existent-id")
