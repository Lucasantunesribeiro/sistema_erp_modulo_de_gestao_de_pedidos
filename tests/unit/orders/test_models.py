"""Unit tests for Order, OrderItem, and OrderStatusHistory models.

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
- OrderItem automatic subtotal calculation.
- OrderItem price snapshot from product.
- OrderItem quantity validation (>= 1).
- OrderItem reverse relation via order.items.
- OrderItem product FK with PROTECT.
- OrderStatusHistory creation and ordering.
- OrderStatusHistory null user (system-initiated).
- OrderStatusHistory reverse relation via order.status_history.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from validate_docbr import CPF as CPFGenerator

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import VALID_TRANSITIONS, OrderStatus
from modules.orders.models import Order, OrderItem, OrderStatusHistory
from modules.products.models import Product

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


def _make_product(**overrides) -> Product:
    """Create and persist a Product for FK references."""
    defaults = {
        "sku": f"SKU-{uuid.uuid4().hex[:8].upper()}",
        "name": "Test Product",
        "price": Decimal("49.90"),
        "stock_quantity": 100,
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


def _make_order_item(order=None, product=None, **overrides) -> OrderItem:
    """Create and persist an OrderItem with sensible defaults."""
    if order is None:
        order = _make_order()
    if product is None:
        product = _make_product()
    defaults = {
        "order": order,
        "product": product,
    }
    defaults.update(overrides)
    return OrderItem.objects.create(**defaults)


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


# ===========================================================================
# OrderItem Tests
# ===========================================================================


# ---------------------------------------------------------------------------
# OrderItem Creation & Subtotal Calculation
# ---------------------------------------------------------------------------


class TestOrderItemCreation:
    """OrderItem creation and automatic subtotal calculation."""

    def test_create_item_with_defaults(self):
        product = _make_product(price=Decimal("25.00"))
        item = _make_order_item(product=product)
        item.refresh_from_db()
        assert item.quantity == 1
        assert item.unit_price == Decimal("25.00")
        assert item.subtotal == Decimal("25.00")

    def test_subtotal_calculated_on_save(self):
        product = _make_product(price=Decimal("10.50"))
        item = _make_order_item(product=product, quantity=3)
        item.refresh_from_db()
        assert item.subtotal == Decimal("31.50")

    def test_subtotal_recalculated_on_update(self):
        product = _make_product(price=Decimal("20.00"))
        item = _make_order_item(product=product, quantity=2)
        assert item.subtotal == Decimal("40.00")
        item.quantity = 5
        item.save()
        item.refresh_from_db()
        assert item.subtotal == Decimal("100.00")

    def test_subtotal_with_decimal_price(self):
        product = _make_product(price=Decimal("9.99"))
        item = _make_order_item(product=product, quantity=4)
        item.refresh_from_db()
        assert item.subtotal == Decimal("39.96")

    def test_id_is_uuid7(self):
        item = _make_order_item()
        assert isinstance(item.id, uuid.UUID)
        assert item.id.version == 7

    def test_timestamps_set_on_create(self):
        item = _make_order_item()
        assert item.created_at is not None
        assert item.updated_at is not None


# ---------------------------------------------------------------------------
# Price Snapshot
# ---------------------------------------------------------------------------


class TestOrderItemPriceSnapshot:
    """unit_price is a snapshot of the product price at creation time."""

    def test_unit_price_auto_filled_from_product(self):
        product = _make_product(price=Decimal("75.00"))
        item = _make_order_item(product=product)
        assert item.unit_price == Decimal("75.00")

    def test_explicit_unit_price_preserved(self):
        product = _make_product(price=Decimal("75.00"))
        item = _make_order_item(
            product=product, unit_price=Decimal("60.00"), quantity=2
        )
        item.refresh_from_db()
        assert item.unit_price == Decimal("60.00")
        assert item.subtotal == Decimal("120.00")

    def test_price_snapshot_not_affected_by_product_update(self):
        product = _make_product(price=Decimal("100.00"))
        item = _make_order_item(product=product, quantity=1)
        assert item.unit_price == Decimal("100.00")

        # Update product price
        product.price = Decimal("150.00")
        product.save()

        # Reload item — unit_price must NOT change
        item.refresh_from_db()
        assert item.unit_price == Decimal("100.00")
        assert item.subtotal == Decimal("100.00")


# ---------------------------------------------------------------------------
# Quantity Validation
# ---------------------------------------------------------------------------


class TestOrderItemQuantity:
    """Quantity must be at least 1."""

    def test_default_quantity_is_one(self):
        item = _make_order_item()
        assert item.quantity == 1

    def test_quantity_greater_than_one(self):
        item = _make_order_item(quantity=10)
        assert item.quantity == 10

    def test_zero_quantity_fails_clean(self):
        item = OrderItem(
            order=_make_order(),
            product=_make_product(),
            quantity=0,
        )
        with pytest.raises(ValidationError) as exc_info:
            item.clean()
        assert "quantity" in exc_info.value.message_dict


# ---------------------------------------------------------------------------
# Order Relation (reverse)
# ---------------------------------------------------------------------------


class TestOrderItemRelation:
    """OrderItem relates to Order via items reverse relation."""

    def test_order_items_reverse_relation(self):
        order = _make_order()
        product1 = _make_product()
        product2 = _make_product()
        _make_order_item(order=order, product=product1)
        _make_order_item(order=order, product=product2)
        assert order.items.count() == 2

    def test_items_belong_to_correct_order(self):
        order1 = _make_order()
        order2 = _make_order()
        product = _make_product()
        item1 = _make_order_item(order=order1, product=product)
        _make_order_item(order=order2, product=product)
        assert list(order1.items.values_list("pk", flat=True)) == [item1.pk]


# ---------------------------------------------------------------------------
# Product FK PROTECT
# ---------------------------------------------------------------------------


class TestOrderItemProductFK:
    """Product FK uses PROTECT — cannot delete product with order items."""

    def test_product_protect_prevents_delete(self):
        product = _make_product()
        _make_order_item(product=product)
        with pytest.raises(ProtectedError):
            product.hard_delete()

    def test_order_cascade_deletes_items(self):
        """Hard-deleting an Order cascades to its items."""
        order = _make_order()
        item = _make_order_item(order=order)
        item_pk = item.pk
        order.hard_delete()
        assert not OrderItem.objects.filter(pk=item_pk).exists()


# ---------------------------------------------------------------------------
# OrderItem Soft Delete
# ---------------------------------------------------------------------------


class TestOrderItemSoftDelete:
    """Soft delete lifecycle inherited from SoftDeleteModel."""

    def test_delete_sets_deleted_at(self):
        item = _make_order_item()
        item.delete()
        item.refresh_from_db()
        assert item.is_deleted is True
        assert item.deleted_at is not None

    def test_soft_deleted_excluded_from_alive(self):
        item = _make_order_item()
        item.delete()
        assert not OrderItem.objects.alive().filter(pk=item.pk).exists()

    def test_restore_after_soft_delete(self):
        item = _make_order_item()
        item.delete()
        item.restore()
        item.refresh_from_db()
        assert item.is_deleted is False


# ---------------------------------------------------------------------------
# OrderItem Display
# ---------------------------------------------------------------------------


class TestOrderItemDisplay:
    """__str__ includes product, quantity, and subtotal."""

    def test_str_representation(self):
        product = _make_product(price=Decimal("15.00"))
        item = _make_order_item(product=product, quantity=3)
        result = str(item)
        assert "x3" in result
        assert "45.00" in result


# ===========================================================================
# OrderStatusHistory Tests
# ===========================================================================


# ---------------------------------------------------------------------------
# OrderStatusHistory Creation
# ---------------------------------------------------------------------------


class TestOrderStatusHistoryCreation:
    """History record creation linked to an order."""

    def test_create_history_record(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            old_status=None,
            new_status=OrderStatus.PENDING,
            notes="Order created.",
        )
        history.refresh_from_db()
        assert history.order_id == order.pk
        assert history.old_status is None
        assert history.new_status == OrderStatus.PENDING
        assert history.notes == "Order created."
        assert history.user is None
        assert history.created_at is not None

    def test_create_transition_record(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.CONFIRMED,
        )
        history.refresh_from_db()
        assert history.old_status == OrderStatus.PENDING
        assert history.new_status == OrderStatus.CONFIRMED

    def test_id_is_uuid7(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            new_status=OrderStatus.PENDING,
        )
        assert isinstance(history.id, uuid.UUID)
        assert history.id.version == 7

    def test_reverse_relation(self):
        order = _make_order()
        OrderStatusHistory.objects.create(
            order=order,
            old_status=None,
            new_status=OrderStatus.PENDING,
        )
        OrderStatusHistory.objects.create(
            order=order,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.CONFIRMED,
        )
        # 1 auto-created by signal on order creation + 2 manual = 3
        assert order.status_history.count() == 3


# ---------------------------------------------------------------------------
# OrderStatusHistory Ordering
# ---------------------------------------------------------------------------


class TestOrderStatusHistoryOrdering:
    """Most recent history record comes first (ordering = ['-created_at'])."""

    def test_most_recent_first(self):
        order = _make_order()
        h1 = OrderStatusHistory.objects.create(
            order=order,
            old_status=None,
            new_status=OrderStatus.PENDING,
        )
        # Small delay to ensure different timestamps
        time.sleep(0.01)
        h2 = OrderStatusHistory.objects.create(
            order=order,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.CONFIRMED,
        )
        history_ids = list(order.status_history.values_list("pk", flat=True))
        assert history_ids[0] == h2.pk
        assert history_ids[1] == h1.pk


# ---------------------------------------------------------------------------
# OrderStatusHistory Null User
# ---------------------------------------------------------------------------


class TestOrderStatusHistoryNullUser:
    """System-initiated changes have user=None."""

    def test_null_user_allowed(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.CANCELLED,
            user=None,
            notes="Cancelled by system due to stock shortage.",
        )
        history.refresh_from_db()
        assert history.user is None
        assert history.notes == "Cancelled by system due to stock shortage."

    def test_default_notes_is_empty(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            new_status=OrderStatus.PENDING,
        )
        assert history.notes == ""


# ---------------------------------------------------------------------------
# OrderStatusHistory CASCADE
# ---------------------------------------------------------------------------


class TestOrderStatusHistoryCascade:
    """Hard-deleting an Order cascades to its history."""

    def test_order_hard_delete_cascades_history(self):
        order = _make_order()
        h = OrderStatusHistory.objects.create(
            order=order,
            new_status=OrderStatus.PENDING,
        )
        h_pk = h.pk
        order.hard_delete()
        assert not OrderStatusHistory.objects.filter(pk=h_pk).exists()


# ---------------------------------------------------------------------------
# OrderStatusHistory Display
# ---------------------------------------------------------------------------


class TestOrderStatusHistoryDisplay:
    """__str__ shows 'ORDER : old_status -> new_status'."""

    def test_str_representation(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.CONFIRMED,
        )
        result = str(history)
        assert order.order_number in result
        assert "PENDING" in result
        assert "CONFIRMED" in result
        assert "->" in result

    def test_str_with_null_old_status(self):
        order = _make_order()
        history = OrderStatusHistory.objects.create(
            order=order,
            old_status=None,
            new_status=OrderStatus.PENDING,
        )
        result = str(history)
        assert "None" in result
        assert "PENDING" in result
