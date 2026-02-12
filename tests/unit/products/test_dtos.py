"""Unit tests for Product DTOs.

Covers:
- CreateProductDTO: validation, SKU normalisation, frozen immutability.
- UpdateProductDTO: optional fields, validation.
- ProductOutputDTO: from_entity factory.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from modules.products.dtos import CreateProductDTO, ProductOutputDTO, UpdateProductDTO
from modules.products.models import Product

pytestmark = pytest.mark.unit


# ===========================================================================
# CreateProductDTO
# ===========================================================================


class TestCreateProductDTOValid:
    def test_create_with_valid_data(self):
        dto = CreateProductDTO(
            sku="SKU-001",
            name="Widget",
            price=Decimal("19.99"),
        )
        assert dto.sku == "SKU-001"
        assert dto.name == "Widget"
        assert dto.price == Decimal("19.99")

    def test_optional_fields_default(self):
        dto = CreateProductDTO(
            sku="SKU-001",
            name="Widget",
            price=Decimal("10.00"),
        )
        assert dto.description == ""
        assert dto.stock_quantity == 0

    def test_optional_fields_can_be_set(self):
        dto = CreateProductDTO(
            sku="SKU-001",
            name="Widget",
            price=Decimal("10.00"),
            description="A fine widget",
            stock_quantity=50,
        )
        assert dto.description == "A fine widget"
        assert dto.stock_quantity == 50

    def test_sku_normalised_to_uppercase(self):
        dto = CreateProductDTO(
            sku="  sku-lower  ",
            name="Widget",
            price=Decimal("10.00"),
        )
        assert dto.sku == "SKU-LOWER"


class TestCreateProductDTOValidation:
    def test_zero_price_raises(self):
        with pytest.raises(ValidationError, match="Price must be greater than zero"):
            CreateProductDTO(
                sku="SKU-001",
                name="Widget",
                price=Decimal("0"),
            )

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError, match="Price must be greater than zero"):
            CreateProductDTO(
                sku="SKU-001",
                name="Widget",
                price=Decimal("-5.00"),
            )

    def test_negative_stock_raises(self):
        with pytest.raises(ValidationError, match="Stock quantity cannot be negative"):
            CreateProductDTO(
                sku="SKU-001",
                name="Widget",
                price=Decimal("10.00"),
                stock_quantity=-1,
            )

    def test_empty_sku_raises(self):
        with pytest.raises(ValidationError, match="SKU must not be empty"):
            CreateProductDTO(
                sku="   ",
                name="Widget",
                price=Decimal("10.00"),
            )


class TestCreateProductDTOFrozen:
    def test_is_immutable(self):
        dto = CreateProductDTO(
            sku="SKU-001",
            name="Widget",
            price=Decimal("10.00"),
        )
        with pytest.raises(ValidationError):
            dto.name = "Changed"


# ===========================================================================
# UpdateProductDTO
# ===========================================================================


class TestUpdateProductDTO:
    def test_all_fields_optional(self):
        dto = UpdateProductDTO()
        assert dto.name is None
        assert dto.price is None
        assert dto.description is None
        assert dto.stock_quantity is None
        assert dto.status is None

    def test_partial_fields(self):
        dto = UpdateProductDTO(name="Updated", price=Decimal("29.99"))
        assert dto.name == "Updated"
        assert dto.price == Decimal("29.99")
        assert dto.description is None

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError, match="Price must be greater than zero"):
            UpdateProductDTO(price=Decimal("-1.00"))

    def test_negative_stock_raises(self):
        with pytest.raises(ValidationError, match="Stock quantity cannot be negative"):
            UpdateProductDTO(stock_quantity=-5)

    def test_is_immutable(self):
        dto = UpdateProductDTO(name="Test")
        with pytest.raises(ValidationError):
            dto.name = "Changed"


# ===========================================================================
# ProductOutputDTO
# ===========================================================================


class TestProductOutputDTOFromEntity:
    def test_from_entity(self):
        product = Product(
            sku="SKU-OUT",
            name="Output Widget",
            price=Decimal("19.99"),
            stock_quantity=10,
            description="A widget",
        )
        product.save()
        dto = ProductOutputDTO.from_entity(product)
        assert dto.id == product.id
        assert dto.sku == "SKU-OUT"
        assert dto.name == "Output Widget"
        assert dto.price == Decimal("19.99")
        assert dto.stock_quantity == 10
        assert dto.description == "A widget"
        assert dto.created_at is not None
        assert dto.updated_at is not None

    def test_is_immutable(self):
        product = Product(
            sku="SKU-FRZ",
            name="Frozen",
            price=Decimal("5.00"),
        )
        product.save()
        dto = ProductOutputDTO.from_entity(product)
        with pytest.raises(ValidationError):
            dto.name = "Changed"
