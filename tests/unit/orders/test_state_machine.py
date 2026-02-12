"""Unit tests for the Order status state machine.

Covers:
- Model-level FSM helpers (can_transition_to, is_terminal).
- All valid transitions (happy path).
- All invalid transitions (skip states, reverse, terminal states).
- History recording on every transition (RN-PED-002/003).
- Full lifecycle through the state machine.
- Domain event hooks are called on transitions.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import TERMINAL_STATES, VALID_TRANSITIONS, OrderStatus
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
        name="FSM Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="fsm@example.com",
        is_active=True,
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="FSM-PROD",
        name="FSM Product",
        price=Decimal("10.00"),
        stock_quantity=100,
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
def pending_order(service, customer, product):
    """An order in PENDING status."""
    dto = CreateOrderDTO(
        customer_id=customer.id,
        items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
    )
    return service.create_order(dto)


# ===========================================================================
# Model-level FSM helpers
# ===========================================================================


class TestCanTransitionTo:
    """Tests for Order.can_transition_to()."""

    def test_pending_to_confirmed(self, pending_order):
        assert pending_order.can_transition_to(OrderStatus.CONFIRMED) is True

    def test_pending_to_cancelled(self, pending_order):
        assert pending_order.can_transition_to(OrderStatus.CANCELLED) is True

    def test_pending_to_shipped_rejected(self, pending_order):
        assert pending_order.can_transition_to(OrderStatus.SHIPPED) is False

    def test_pending_to_delivered_rejected(self, pending_order):
        assert pending_order.can_transition_to(OrderStatus.DELIVERED) is False

    def test_pending_to_separated_rejected(self, pending_order):
        assert pending_order.can_transition_to(OrderStatus.SEPARATED) is False


class TestIsTerminal:
    """Tests for Order.is_terminal property."""

    def test_pending_is_not_terminal(self, pending_order):
        assert pending_order.is_terminal is False

    def test_delivered_is_terminal(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)
        assert order.is_terminal is True

    def test_cancelled_is_terminal(self, service, pending_order):
        order = service.cancel_order(pending_order.id)
        assert order.is_terminal is True

    def test_terminal_states_constant(self):
        assert OrderStatus.DELIVERED in TERMINAL_STATES
        assert OrderStatus.CANCELLED in TERMINAL_STATES
        assert OrderStatus.PENDING not in TERMINAL_STATES


# ===========================================================================
# Valid Transitions (Happy Path)
# ===========================================================================


class TestValidTransitions:
    """Every valid transition from VALID_TRANSITIONS must succeed."""

    def test_pending_to_confirmed(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        assert order.status == OrderStatus.CONFIRMED

    def test_confirmed_to_separated(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        assert order.status == OrderStatus.SEPARATED

    def test_separated_to_shipped(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        assert order.status == OrderStatus.SHIPPED

    def test_shipped_to_delivered(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)
        assert order.status == OrderStatus.DELIVERED

    def test_pending_to_cancelled(self, service, pending_order):
        order = service.cancel_order(pending_order.id)
        assert order.status == OrderStatus.CANCELLED

    def test_confirmed_to_cancelled(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.cancel_order(order.id)
        assert order.status == OrderStatus.CANCELLED


# ===========================================================================
# Invalid Transitions
# ===========================================================================


class TestInvalidTransitions:
    """Transitions not in VALID_TRANSITIONS must raise InvalidOrderStatus."""

    def test_pending_to_separated_rejected(self, service, pending_order):
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(pending_order.id, OrderStatus.SEPARATED)

    def test_pending_to_shipped_rejected(self, service, pending_order):
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(pending_order.id, OrderStatus.SHIPPED)

    def test_pending_to_delivered_rejected(self, service, pending_order):
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(pending_order.id, OrderStatus.DELIVERED)

    def test_confirmed_to_shipped_rejected(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(order.id, OrderStatus.SHIPPED)

    def test_separated_to_confirmed_rejected(self, service, pending_order):
        """Reverse transition forbidden."""
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(order.id, OrderStatus.CONFIRMED)

    def test_shipped_to_pending_rejected(self, service, pending_order):
        """Reverse transition forbidden."""
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(order.id, OrderStatus.PENDING)

    def test_update_nonexistent_order_raises(self, service):
        with pytest.raises(OrderNotFound):
            service.update_status(uuid4(), OrderStatus.CONFIRMED)


class TestTerminalStateImmutability:
    """Terminal states (DELIVERED, CANCELLED) must reject all transitions."""

    def test_delivered_to_any_rejected(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)

        for target in OrderStatus:
            if target == OrderStatus.DELIVERED:
                continue
            with pytest.raises(InvalidOrderStatus):
                service.update_status(order.id, target)

    def test_cancelled_to_any_rejected(self, service, pending_order):
        order = service.cancel_order(pending_order.id)

        for target in OrderStatus:
            if target == OrderStatus.CANCELLED:
                continue
            with pytest.raises(InvalidOrderStatus):
                service.update_status(order.id, target)

    def test_cancel_already_cancelled_rejected(self, service, pending_order):
        order = service.cancel_order(pending_order.id)
        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)

    def test_cancel_delivered_rejected(self, service, pending_order):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)
        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)


# ===========================================================================
# History Recording (RN-PED-002/003)
# ===========================================================================


class TestStatusHistory:
    """Every status transition must produce a history record."""

    def test_creation_records_initial_history(self, pending_order):
        history = list(pending_order.status_history.all())
        assert len(history) == 1
        assert history[0].new_status == OrderStatus.PENDING
        assert history[0].notes == "Order created"

    def test_transition_records_old_and_new_status(self, service, pending_order):
        service.update_status(
            pending_order.id, OrderStatus.CONFIRMED, notes="Payment OK"
        )
        history = OrderStatusHistory.objects.filter(order=pending_order).order_by(
            "created_at"
        )
        last = history.last()
        assert last.old_status == OrderStatus.PENDING
        assert last.new_status == OrderStatus.CONFIRMED
        assert last.notes == "Payment OK"

    def test_full_lifecycle_produces_correct_history_count(
        self, service, pending_order
    ):
        order = service.update_status(pending_order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)

        # 1 (creation) + 4 transitions = 5 records
        count = OrderStatusHistory.objects.filter(order=pending_order).count()
        assert count == 5

    def test_cancellation_records_history(self, service, pending_order):
        service.cancel_order(pending_order.id, notes="No longer needed")
        history = OrderStatusHistory.objects.filter(
            order=pending_order, new_status=OrderStatus.CANCELLED
        )
        assert history.count() == 1
        assert history.first().notes == "No longer needed"


# ===========================================================================
# VALID_TRANSITIONS Exhaustive Coverage
# ===========================================================================


class TestTransitionsMapCompleteness:
    """Verify the VALID_TRANSITIONS map covers all OrderStatus values."""

    def test_all_statuses_have_transition_entry(self):
        for status in OrderStatus:
            assert (
                status in VALID_TRANSITIONS
            ), f"{status} missing from VALID_TRANSITIONS"

    def test_terminal_states_have_empty_transitions(self):
        for state in TERMINAL_STATES:
            assert (
                VALID_TRANSITIONS[state] == set()
            ), f"Terminal state {state} should have no valid transitions"

    def test_no_self_transitions(self):
        for state, targets in VALID_TRANSITIONS.items():
            assert state not in targets, f"Self-transition not allowed for {state}"


# ===========================================================================
# Domain Event Hooks
# ===========================================================================


class TestDomainEventHooks:
    """Verify that domain event hooks fire on transitions."""

    def test_on_order_created_fires(self, service, customer, product):
        dto = CreateOrderDTO(
            customer_id=customer.id,
            items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
        )
        with patch.object(service, "_on_order_created") as mock_hook:
            service.create_order(dto)
            mock_hook.assert_called_once()

    def test_dispatch_status_event_fires(self, service, pending_order):
        with patch.object(service, "_dispatch_status_event") as mock_hook:
            service.update_status(pending_order.id, OrderStatus.CONFIRMED)
            mock_hook.assert_called_once()
            call_args = mock_hook.call_args[0]
            assert call_args[1] == OrderStatus.PENDING
            assert call_args[2] == OrderStatus.CONFIRMED

    def test_on_order_cancelled_fires(self, service, pending_order):
        with patch.object(service, "_on_order_cancelled") as mock_hook:
            service.cancel_order(pending_order.id)
            mock_hook.assert_called_once()
