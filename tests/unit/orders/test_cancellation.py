"""Unit tests for order cancellation with stock release.

Covers:
- Cancel from PENDING — status, history, and stock restored (RN-EST-005).
- Cancel from CONFIRMED — status, history, and stock restored (RN-EST-006).
- Cancel from terminal/non-cancellable states — rejected.
- Atomicity: cancelled order + stock restored in the same transaction.
- updated_at is refreshed on cancellation.
- Cancellation reason recorded in history.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
from modules.orders.exceptions import InvalidOrderStatus, OrderNotFound
from modules.orders.models import OrderStatusHistory
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.services import OrderService
from modules.products.models import Product, ProductStatus
from modules.products.repositories.django_repository import ProductDjangoRepository

pytestmark = pytest.mark.unit

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Cancel Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="cancel@example.com",
        is_active=True,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="CANCEL-A",
        name="Cancel Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="CANCEL-B",
        name="Cancel Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def service():
    from modules.customers.repositories.django_repository import (
        CustomerDjangoRepository,
    )

    return OrderService(
        order_repository=OrderDjangoRepository(),
        customer_repository=CustomerDjangoRepository(),
        product_repository=ProductDjangoRepository(),
    )


@pytest.fixture()
def order_dto(customer, product_a, product_b):
    return CreateOrderDTO(
        customer_id=customer.id,
        items=[
            CreateOrderItemDTO(product_id=product_a.id, quantity=5),
            CreateOrderItemDTO(product_id=product_b.id, quantity=3),
        ],
        notes="Order to cancel",
    )


@pytest.fixture()
def pending_order(service, order_dto):
    return service.create_order(order_dto)


@pytest.fixture()
def confirmed_order(service, order_dto):
    order = service.create_order(order_dto)
    return service.update_status(order.id, OrderStatus.CONFIRMED)


# ===========================================================================
# Cancel from PENDING
# ===========================================================================


class TestCancelPendingOrder:
    def test_status_changes_to_cancelled(self, service, pending_order):
        cancelled = service.cancel_order(pending_order.id)
        assert cancelled.status == OrderStatus.CANCELLED

    def test_stock_restored_to_original(
        self, service, pending_order, product_a, product_b
    ):
        # After creation: A=95, B=47
        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 95
        assert product_b.stock_quantity == 47

        service.cancel_order(pending_order.id)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert product_b.stock_quantity == 50

    def test_records_cancellation_history(self, service, pending_order):
        service.cancel_order(pending_order.id, notes="Customer changed mind")

        history = OrderStatusHistory.objects.filter(
            order=pending_order, new_status=OrderStatus.CANCELLED
        )
        assert history.count() == 1
        record = history.first()
        assert record.old_status == OrderStatus.PENDING
        assert record.notes == "Customer changed mind"

    def test_default_cancellation_note(self, service, pending_order):
        service.cancel_order(pending_order.id)

        history = OrderStatusHistory.objects.filter(
            order=pending_order, new_status=OrderStatus.CANCELLED
        ).first()
        assert history.notes == "Order cancelled"

    def test_updated_at_refreshed(self, service, pending_order):
        original_updated = pending_order.updated_at
        cancelled = service.cancel_order(pending_order.id)
        assert cancelled.updated_at >= original_updated


# ===========================================================================
# Cancel from CONFIRMED
# ===========================================================================


class TestCancelConfirmedOrder:
    def test_status_changes_to_cancelled(self, service, confirmed_order):
        cancelled = service.cancel_order(confirmed_order.id)
        assert cancelled.status == OrderStatus.CANCELLED

    def test_stock_restored_after_confirm_cancel(
        self, service, confirmed_order, product_a, product_b
    ):
        # Stock was deducted during creation: A=95, B=47
        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 95
        assert product_b.stock_quantity == 47

        service.cancel_order(confirmed_order.id)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert product_b.stock_quantity == 50

    def test_records_history_with_confirmed_as_old(self, service, confirmed_order):
        service.cancel_order(confirmed_order.id, notes="Admin override")

        history = OrderStatusHistory.objects.filter(
            order=confirmed_order, new_status=OrderStatus.CANCELLED
        ).first()
        assert history.old_status == OrderStatus.CONFIRMED
        assert history.notes == "Admin override"

    def test_total_history_count(self, service, confirmed_order):
        service.cancel_order(confirmed_order.id)
        # 1 (creation) + 1 (confirm) + 1 (cancel) = 3
        count = OrderStatusHistory.objects.filter(order=confirmed_order).count()
        assert count == 3


# ===========================================================================
# Cancel from non-cancellable states
# ===========================================================================


class TestCancelForbiddenStates:
    def test_cancel_separated_raises(self, service, order_dto):
        order = service.create_order(order_dto)
        order = service.update_status(order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)

        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)

    def test_cancel_shipped_raises(self, service, order_dto):
        order = service.create_order(order_dto)
        order = service.update_status(order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)

        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)

    def test_cancel_delivered_raises(self, service, order_dto):
        order = service.create_order(order_dto)
        order = service.update_status(order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)

        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)

    def test_cancel_already_cancelled_raises(self, service, pending_order):
        service.cancel_order(pending_order.id)

        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(pending_order.id)

    def test_cancel_nonexistent_order_raises(self, service):
        with pytest.raises(OrderNotFound):
            service.cancel_order(uuid4())


# ===========================================================================
# Atomicity — stock not released on forbidden cancel
# ===========================================================================


class TestCancelAtomicity:
    def test_stock_unchanged_when_cancel_rejected(
        self, service, order_dto, product_a, product_b
    ):
        """If cancel_order raises, stock must remain deducted."""
        order = service.create_order(order_dto)
        order = service.update_status(order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        stock_a_before = product_a.stock_quantity
        stock_b_before = product_b.stock_quantity

        with pytest.raises(InvalidOrderStatus):
            service.cancel_order(order.id)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == stock_a_before
        assert product_b.stock_quantity == stock_b_before

    def test_multi_item_stock_all_restored(
        self, service, pending_order, product_a, product_b
    ):
        """All items' stock must be restored in a single atomic operation."""
        service.cancel_order(pending_order.id)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert product_b.stock_quantity == 50
