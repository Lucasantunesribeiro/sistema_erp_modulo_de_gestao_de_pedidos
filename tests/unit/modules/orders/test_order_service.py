"""Unit tests for OrderService with mocked dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from modules.orders.constants import OrderStatus
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
from modules.orders.exceptions import (
    CustomerNotFound,
    InactiveCustomer,
    InactiveProduct,
    InsufficientStock,
    InvalidOrderStatus,
    OrderNotFound,
    ProductNotFound,
)
from modules.orders.services import OrderService

pytestmark = pytest.mark.unit


@dataclass
class StubCustomer:
    id: UUID
    is_active: bool = True


@dataclass
class StubProduct:
    id: UUID
    sku: str
    status: str
    stock_quantity: int
    price: Decimal
    saved_update_fields: list[str] | None = None

    def save(self, *args, **kwargs) -> None:
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            self.saved_update_fields = list(update_fields)


class StubProductQuery:
    def __init__(self, products_by_id: dict[UUID, StubProduct]):
        self._products = products_by_id
        self._current_id: UUID | None = None

    def filter(self, id=None, **kwargs):
        self._current_id = id
        return self

    def first(self):
        return self._products.get(self._current_id)


def _call_create_order(service: OrderService, dto: CreateOrderDTO):
    return OrderService.create_order.__wrapped__(service, dto)


def _call_update_status(
    service: OrderService, order_id: UUID, new_status: str, notes: str = ""
):
    return OrderService.update_status.__wrapped__(service, order_id, new_status, notes)


def _patch_products(products_by_id: dict[UUID, StubProduct]):
    query = StubProductQuery(products_by_id)
    product_cls = MagicMock()
    product_cls.objects.select_for_update.return_value = query
    return patch("modules.products.models.Product", product_cls), product_cls


@pytest.fixture()
def service_and_repos():
    order_repo = MagicMock()
    customer_repo = MagicMock()
    product_repo = MagicMock()
    service = OrderService(order_repo, customer_repo, product_repo)
    return service, order_repo, customer_repo, product_repo


class TestCreateOrder:
    def test_create_order_success_calls_repository_create(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_id = uuid4()
        customer_repo.get_by_id.return_value = StubCustomer(customer_id, True)

        product_a = StubProduct(
            id=uuid4(),
            sku="UNIT-A",
            status="active",
            stock_quantity=10,
            price=Decimal("10.00"),
        )
        product_b = StubProduct(
            id=uuid4(),
            sku="UNIT-B",
            status="active",
            stock_quantity=5,
            price=Decimal("25.50"),
        )

        dto = CreateOrderDTO(
            customer_id=customer_id,
            items=[
                CreateOrderItemDTO(product_id=product_a.id, quantity=2),
                CreateOrderItemDTO(product_id=product_b.id, quantity=1),
            ],
            notes="Unit order",
        )

        order = MagicMock()
        order.id = uuid4()
        order_repo.create.return_value = order
        order_repo.get_by_id.return_value = order

        patcher, _ = _patch_products({product_a.id: product_a, product_b.id: product_b})
        with patcher:
            result = _call_create_order(service, dto)

        assert result is order
        order_repo.create.assert_called_once()
        order_repo.save.assert_called_once_with(order)
        order_repo.add_history.assert_called_once_with(
            order_id=order.id,
            status=OrderStatus.PENDING,
            notes="Order created",
        )
        order_repo.get_by_id.assert_called_once_with(str(order.id))

        payload = order_repo.create.call_args.args[0]
        items = sorted(payload["items"], key=lambda i: str(i["product_id"]))
        expected_items = sorted(
            [
                {
                    "product_id": product_a.id,
                    "quantity": 2,
                    "unit_price": product_a.price,
                },
                {
                    "product_id": product_b.id,
                    "quantity": 1,
                    "unit_price": product_b.price,
                },
            ],
            key=lambda i: str(i["product_id"]),
        )
        assert items == expected_items
        assert payload["customer_id"] == customer_id
        assert payload["notes"] == "Unit order"

        assert product_a.stock_quantity == 8
        assert product_b.stock_quantity == 4
        assert "stock_quantity" in (product_a.saved_update_fields or [])
        assert "stock_quantity" in (product_b.saved_update_fields or [])

    def test_create_order_empty_items_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CreateOrderDTO(customer_id=uuid4(), items=[])

    def test_create_order_customer_not_found_raises(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_repo.get_by_id.return_value = None

        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
        )

        patcher, product_cls = _patch_products({})
        with patcher:
            with pytest.raises(CustomerNotFound):
                _call_create_order(service, dto)

        assert not product_cls.objects.select_for_update.called
        order_repo.create.assert_not_called()

    def test_create_order_inactive_customer_raises(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_id = uuid4()
        customer_repo.get_by_id.return_value = StubCustomer(customer_id, False)

        dto = CreateOrderDTO(
            customer_id=customer_id,
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
        )

        patcher, product_cls = _patch_products({})
        with patcher:
            with pytest.raises(InactiveCustomer):
                _call_create_order(service, dto)

        assert not product_cls.objects.select_for_update.called
        order_repo.create.assert_not_called()

    def test_create_order_product_not_found_raises(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_id = uuid4()
        customer_repo.get_by_id.return_value = StubCustomer(customer_id, True)
        missing_id = uuid4()

        dto = CreateOrderDTO(
            customer_id=customer_id,
            items=[CreateOrderItemDTO(product_id=missing_id, quantity=1)],
        )

        patcher, _ = _patch_products({})
        with patcher:
            with pytest.raises(ProductNotFound):
                _call_create_order(service, dto)

        order_repo.create.assert_not_called()

    def test_create_order_inactive_product_raises(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_id = uuid4()
        customer_repo.get_by_id.return_value = StubCustomer(customer_id, True)

        product = StubProduct(
            id=uuid4(),
            sku="UNIT-INACTIVE",
            status="inactive",
            stock_quantity=10,
            price=Decimal("12.00"),
        )

        dto = CreateOrderDTO(
            customer_id=customer_id,
            items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
        )

        patcher, _ = _patch_products({product.id: product})
        with patcher:
            with pytest.raises(InactiveProduct):
                _call_create_order(service, dto)

        order_repo.create.assert_not_called()

    def test_create_order_insufficient_stock_raises(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        customer_id = uuid4()
        customer_repo.get_by_id.return_value = StubCustomer(customer_id, True)

        product = StubProduct(
            id=uuid4(),
            sku="UNIT-LOW",
            status="active",
            stock_quantity=0,
            price=Decimal("9.00"),
        )
        dto = CreateOrderDTO(
            customer_id=customer_id,
            items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
        )

        patcher, _ = _patch_products({product.id: product})
        with patcher:
            with pytest.raises(InsufficientStock):
                _call_create_order(service, dto)

        assert product.saved_update_fields is None
        order_repo.create.assert_not_called()

    def test_create_order_idempotency_returns_existing(self, service_and_repos):
        service, order_repo, customer_repo, _ = service_and_repos
        existing_order = MagicMock()
        existing_order.id = uuid4()
        order_repo.get_by_idempotency_key.return_value = existing_order

        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
            idempotency_key="idem-123",
        )

        patcher, product_cls = _patch_products({})
        with patcher:
            result = _call_create_order(service, dto)

        assert result is existing_order
        customer_repo.get_by_id.assert_not_called()
        assert not product_cls.objects.select_for_update.called
        order_repo.create.assert_not_called()
        order_repo.add_history.assert_not_called()


class TestUpdateStatus:
    def test_update_status_valid_transition(self, service_and_repos):
        service, order_repo, _, _ = service_and_repos
        order = MagicMock()
        order.id = uuid4()
        order.status = OrderStatus.PENDING
        order.can_transition_to.return_value = True
        order_repo.get_for_update.return_value = order
        order_repo.get_by_id.return_value = order

        result = _call_update_status(
            service, order.id, OrderStatus.CONFIRMED, notes="Approved"
        )

        assert result is order
        assert order.status == OrderStatus.CONFIRMED
        order_repo.save.assert_called_once_with(order)
        order_repo.add_history.assert_called_once_with(
            order_id=order.id,
            status=OrderStatus.CONFIRMED,
            notes="Approved",
            old_status=OrderStatus.PENDING,
        )

    def test_update_status_invalid_transition_raises(self, service_and_repos):
        service, order_repo, _, _ = service_and_repos
        order = MagicMock()
        order.id = uuid4()
        order.status = OrderStatus.CANCELLED
        order.can_transition_to.return_value = False
        order_repo.get_for_update.return_value = order

        with pytest.raises(InvalidOrderStatus):
            _call_update_status(service, order.id, OrderStatus.PENDING)

        order.save.assert_not_called()
        order_repo.save.assert_not_called()
        order_repo.add_history.assert_not_called()

    def test_update_status_order_not_found_raises(self, service_and_repos):
        service, order_repo, _, _ = service_and_repos
        order_repo.get_for_update.return_value = None

        with pytest.raises(OrderNotFound):
            _call_update_status(service, uuid4(), OrderStatus.CONFIRMED)
