"""Unit tests for domain events registration on entities."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from modules.orders.constants import OrderStatus
from modules.orders.events import OrderCreated
from modules.orders.models import Order

pytestmark = pytest.mark.unit


def test_order_registers_and_clears_domain_events():
    order = Order(
        customer_id=uuid4(),
        order_number="ORD-TEST-000001",
        status=OrderStatus.PENDING,
        total_amount=Decimal("0.00"),
    )

    assert order.domain_events == []

    event = OrderCreated(aggregate_id=order.id)
    order.add_domain_event(event)

    assert order.domain_events == [event]
    assert event.event_name == "OrderCreated"

    order.clear_domain_events()
    assert order.domain_events == []
