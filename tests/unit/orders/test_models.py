"""Unit tests for the Order model.

Covers:
- Valid creation with auto-generated order_number.
- Order number format and uniqueness.
- Default status is PENDING.
- Idempotency key uniqueness constraint.
- Customer FK with PROTECT.
- Soft delete lifecycle (inherited from SoftDeleteModel).
- __str__ representation.
- Status choices from OrderStatus.
- VALID_TRANSITIONS map correctness.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from validate_docbr import CPF as CPFGenerator

from django.db import IntegrityError
from django.db.models import ProtectedError

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import VALID_TRANSITIONS, OrderStatus
from modules.orders.models import Order

pytestmark = pytest.mark.unit

_cpf_gen = CPFGenerator()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_customer(**overrides) -> Customer:
    """Create and persist a Customer for FK references."""
    defaults = {
        "name": "Test Customer",
        "document": _cpf_gen.generate(),
        "document_type": DocumentType.CPF,
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
    }
    defaults.update(overrides)
    return Customer.objects.create(**defaults)


def _make_order(customer=None, **overrides) -> Order:
    """Create and persist an Order with sensible defaults."""
    if customer is None:
        customer = _make_customer()
    defaults = {
        "customer": customer,
    }
    defaults.update(overrides)
    return Order.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestOrderCreation:
    """Happy-path order creation."""

    def test_create_order_with_defaults(self):
        customer = _make_customer()
        order = _make_order(customer=customer)
        order.refresh_from_db()
        assert order.customer_id == customer.pk
        assert order.status == OrderStatus.PENDING
        assert order.total_amount == Decimal("0.00")
        assert order.notes == ""
        assert order.idempotency_key is None
        assert order.is_deleted is False

    def test_id_is_uuid7(self):
        order = _make_order()
        assert isinstance(order.id, uuid.UUID)
        assert order.id.version == 7

    def test_timestamps_set_on_create(self):
        order = _make_order()
        assert order.created_at is not None
        assert order.updated_at is not None


# ---------------------------------------------------------------------------
# Order Number
# ---------------------------------------------------------------------------


class TestOrderNumber:
    """Order number is auto-generated, human-readable, and unique."""

    def test_order_number_auto_generated(self):
        order = _make_order()
        assert order.order_number is not None
        assert order.order_number != ""

    def test_order_number_format(self):
        order = _make_order()
        # Format: ORD-YYYYMMDD-XXXXXX
        assert order.order_number.startswith("ORD-")
        parts = order.order_number.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # hex suffix

    def test_order_numbers_are_unique(self):
        o1 = _make_order()
        o2 = _make_order()
        assert o1.order_number != o2.order_number

    def test_explicit_order_number_preserved(self):
        customer = _make_customer()
        order = Order.objects.create(
            customer=customer,
            order_number="CUSTOM-001",
        )
        assert order.order_number == "CUSTOM-001"

    def test_duplicate_order_number_raises(self):
        customer = _make_customer()
        Order.objects.create(customer=customer, order_number="DUP-001")
        with pytest.raises(IntegrityError):
            Order.objects.create(customer=customer, order_number="DUP-001")

    def test_retry_on_collision(self):
        """generate_order_number retry loop handles collisions."""
        customer = _make_customer()
        existing = _make_order(customer=customer)
        colliding_number = existing.order_number

        call_count = 0
        original_generate = Order.generate_order_number

        def mock_generate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return colliding_number  # first attempt collides
            return original_generate()  # subsequent attempts succeed

        with patch.object(Order, "generate_order_number", side_effect=mock_generate):
            new_order = Order.objects.create(customer=customer)

        assert new_order.order_number != colliding_number
        assert call_count >= 2


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestOrderStatus:
    """Default status and choices."""

    def test_default_status_is_pending(self):
        order = _make_order()
        assert order.status == OrderStatus.PENDING

    def test_can_set_status(self):
        order = _make_order()
        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=["status"])
        order.refresh_from_db()
        assert order.status == OrderStatus.CONFIRMED

    def test_all_statuses_in_choices(self):
        values = {c[0] for c in OrderStatus.choices}
        expected = {
            "PENDING",
            "CONFIRMED",
            "SEPARATED",
            "SHIPPED",
            "DELIVERED",
            "CANCELLED",
        }
        assert values == expected


# ---------------------------------------------------------------------------
# Valid Transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """VALID_TRANSITIONS map reflects BUSINESS_RULES.md section 3.2."""

    def test_pending_transitions(self):
        assert VALID_TRANSITIONS[OrderStatus.PENDING] == {
            OrderStatus.CONFIRMED,
            OrderStatus.CANCELLED,
        }

    def test_confirmed_transitions(self):
        assert VALID_TRANSITIONS[OrderStatus.CONFIRMED] == {
            OrderStatus.SEPARATED,
            OrderStatus.CANCELLED,
        }

    def test_separated_transitions(self):
        assert VALID_TRANSITIONS[OrderStatus.SEPARATED] == {OrderStatus.SHIPPED}

    def test_shipped_transitions(self):
        assert VALID_TRANSITIONS[OrderStatus.SHIPPED] == {OrderStatus.DELIVERED}

    def test_delivered_is_terminal(self):
        assert VALID_TRANSITIONS[OrderStatus.DELIVERED] == set()

    def test_cancelled_is_terminal(self):
        assert VALID_TRANSITIONS[OrderStatus.CANCELLED] == set()

    def test_all_statuses_have_transitions_defined(self):
        for status in OrderStatus:
            assert status in VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# Idempotency Key
# ---------------------------------------------------------------------------


class TestIdempotencyKey:
    """Idempotency key uniqueness."""

    def test_idempotency_key_is_optional(self):
        order = _make_order()
        assert order.idempotency_key is None

    def test_duplicate_idempotency_key_raises(self):
        customer = _make_customer()
        _make_order(customer=customer, idempotency_key="KEY-001")
        with pytest.raises(IntegrityError):
            _make_order(customer=customer, idempotency_key="KEY-001")

    def test_multiple_null_idempotency_keys_allowed(self):
        """MySQL allows multiple NULLs in a UNIQUE column."""
        o1 = _make_order(idempotency_key=None)
        o2 = _make_order(idempotency_key=None)
        assert o1.pk != o2.pk  # both saved successfully


# ---------------------------------------------------------------------------
# Customer FK
# ---------------------------------------------------------------------------


class TestCustomerFK:
    """Customer FK uses PROTECT."""

    def test_customer_protect_prevents_delete(self):
        customer = _make_customer()
        _make_order(customer=customer)
        with pytest.raises(ProtectedError):
            customer.hard_delete()

    def test_order_references_customer(self):
        customer = _make_customer()
        order = _make_order(customer=customer)
        order.refresh_from_db()
        assert order.customer_id == customer.pk


# ---------------------------------------------------------------------------
# Soft Delete
# ---------------------------------------------------------------------------


class TestOrderSoftDelete:
    """Soft delete via inherited SoftDeleteModel."""

    def test_delete_sets_deleted_at(self):
        order = _make_order()
        order.delete()
        order.refresh_from_db()
        assert order.is_deleted is True
        assert order.deleted_at is not None

    def test_soft_deleted_excluded_from_alive(self):
        order = _make_order()
        order.delete()
        assert not Order.objects.alive().filter(pk=order.pk).exists()

    def test_restore_after_soft_delete(self):
        order = _make_order()
        order.delete()
        order.restore()
        order.refresh_from_db()
        assert order.is_deleted is False

    def test_hard_delete_removes_from_db(self):
        order = _make_order()
        pk = order.pk
        order.hard_delete()
        assert not Order.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class TestOrderDisplay:
    """__str__ returns 'ORDER_NUMBER (STATUS)'."""

    def test_str_representation(self):
        order = _make_order()
        result = str(order)
        assert order.order_number in result
        assert "PENDING" in result
