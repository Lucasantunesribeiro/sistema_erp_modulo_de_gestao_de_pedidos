"""Unit tests for Order DTOs.

Covers:
- CreateOrderItemDTO: quantity validation, frozen immutability.
- CreateOrderDTO: items list validation, duplicate product check.
- OrderOutputDTO: from_entity factory with nested items and history.
- StatusHistoryDTO: from_entity factory.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.orders.dtos import (
    CreateOrderDTO,
    CreateOrderItemDTO,
    OrderItemOutputDTO,
    OrderOutputDTO,
    StatusHistoryDTO,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# CreateOrderItemDTO
# ===========================================================================


class TestCreateOrderItemDTOValid:
    def test_valid_item(self):
        dto = CreateOrderItemDTO(product_id=uuid4(), quantity=3)
        assert dto.quantity == 3

    def test_minimum_quantity(self):
        dto = CreateOrderItemDTO(product_id=uuid4(), quantity=1)
        assert dto.quantity == 1


class TestCreateOrderItemDTOValidation:
    def test_zero_quantity_raises(self):
        with pytest.raises(ValidationError, match="Quantity must be at least 1"):
            CreateOrderItemDTO(product_id=uuid4(), quantity=0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValidationError, match="Quantity must be at least 1"):
            CreateOrderItemDTO(product_id=uuid4(), quantity=-1)


class TestCreateOrderItemDTOFrozen:
    def test_is_immutable(self):
        dto = CreateOrderItemDTO(product_id=uuid4(), quantity=2)
        with pytest.raises(ValidationError):
            dto.quantity = 5


# ===========================================================================
# CreateOrderDTO
# ===========================================================================


class TestCreateOrderDTOValid:
    def test_valid_order(self):
        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
        )
        assert len(dto.items) == 1
        assert dto.notes == ""

    def test_with_notes(self):
        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
            notes="Rush delivery",
        )
        assert dto.notes == "Rush delivery"

    def test_multiple_items(self):
        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[
                CreateOrderItemDTO(product_id=uuid4(), quantity=2),
                CreateOrderItemDTO(product_id=uuid4(), quantity=5),
            ],
        )
        assert len(dto.items) == 2


class TestCreateOrderDTOValidation:
    def test_empty_items_raises(self):
        with pytest.raises(ValidationError, match="at least one item"):
            CreateOrderDTO(customer_id=uuid4(), items=[])

    def test_duplicate_product_ids_raises(self):
        product_id = uuid4()
        with pytest.raises(ValidationError, match="Duplicate product IDs"):
            CreateOrderDTO(
                customer_id=uuid4(),
                items=[
                    CreateOrderItemDTO(product_id=product_id, quantity=1),
                    CreateOrderItemDTO(product_id=product_id, quantity=2),
                ],
            )


class TestCreateOrderDTOFrozen:
    def test_is_immutable(self):
        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
        )
        with pytest.raises(ValidationError):
            dto.notes = "Changed"


# ===========================================================================
# OrderItemOutputDTO
# ===========================================================================


class TestOrderItemOutputDTO:
    def test_valid_output(self):
        dto = OrderItemOutputDTO(
            id=uuid4(),
            product_id=uuid4(),
            product_name="Widget",
            product_sku="SKU-001",
            quantity=2,
            unit_price=Decimal("10.00"),
            subtotal=Decimal("20.00"),
        )
        assert dto.quantity == 2
        assert dto.subtotal == Decimal("20.00")


# ===========================================================================
# StatusHistoryDTO
# ===========================================================================


class TestStatusHistoryDTO:
    def test_valid_output(self):
        from datetime import datetime, timezone

        dto = StatusHistoryDTO(
            id=uuid4(),
            old_status="PENDING",
            new_status="CONFIRMED",
            notes="Approved",
            created_at=datetime.now(tz=timezone.utc),
        )
        assert dto.old_status == "PENDING"
        assert dto.new_status == "CONFIRMED"

    def test_old_status_can_be_none(self):
        from datetime import datetime, timezone

        dto = StatusHistoryDTO(
            id=uuid4(),
            old_status=None,
            new_status="PENDING",
            notes="",
            created_at=datetime.now(tz=timezone.utc),
        )
        assert dto.old_status is None


# ===========================================================================
# OrderOutputDTO
# ===========================================================================


class TestOrderOutputDTO:
    def test_from_entity(self, customer, product_a):
        """Test from_entity with a real Order aggregate."""
        from modules.orders.constants import OrderStatus
        from modules.orders.repositories.django_repository import OrderDjangoRepository

        repo = OrderDjangoRepository()
        order = repo.create(
            {
                "customer_id": customer.id,
                "items": [
                    {
                        "product_id": product_a.id,
                        "quantity": 3,
                        "unit_price": product_a.price,
                    },
                ],
            }
        )
        repo.add_history(order.id, OrderStatus.CONFIRMED, notes="Test")

        # Re-fetch with prefetch
        order = repo.get_by_id(str(order.id))
        dto = OrderOutputDTO.from_entity(order)

        assert dto.id == order.id
        assert dto.order_number == order.order_number
        assert dto.customer_id == customer.id
        assert len(dto.items) == 1
        assert dto.items[0].quantity == 3
        assert dto.items[0].product_name == "Product A"
        assert len(dto.history) == 1
        assert dto.history[0].new_status == OrderStatus.CONFIRMED

    def test_is_immutable(self, customer, product_a):
        from modules.orders.repositories.django_repository import OrderDjangoRepository

        repo = OrderDjangoRepository()
        order = repo.create(
            {
                "customer_id": customer.id,
                "items": [
                    {
                        "product_id": product_a.id,
                        "quantity": 1,
                        "unit_price": product_a.price,
                    },
                ],
            }
        )
        order = repo.get_by_id(str(order.id))
        dto = OrderOutputDTO.from_entity(order)
        with pytest.raises(ValidationError):
            dto.notes = "Changed"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer():
    from modules.customers.models import Customer, DocumentType

    return Customer.objects.create(
        name="Test Customer",
        document="59860184275",
        document_type=DocumentType.CPF,
        email="dto-test@example.com",
    )


@pytest.fixture()
def product_a():
    from modules.products.models import Product

    return Product.objects.create(
        sku="DTO-PROD-A",
        name="Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
    )
