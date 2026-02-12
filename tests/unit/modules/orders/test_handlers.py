"""Unit tests for Orders event handlers and in-memory bus."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from modules.orders.events import OrderCancelled, OrderCreated, OrderStatusChanged
from modules.orders.handlers import (
    OrderCancelledHandler,
    OrderCreatedHandler,
    OrderStatusChangedHandler,
)
from shared.infrastructure.bus import InMemoryEventBus

pytestmark = pytest.mark.unit


def test_order_created_handler_logs(caplog):
    handler = OrderCreatedHandler()
    event = OrderCreated(aggregate_id=uuid4())

    with caplog.at_level(logging.INFO, logger="modules.orders.handlers"):
        handler.handle(event)

    assert any(
        "Processando evento de criação do pedido" in record.getMessage()
        for record in caplog.records
    )


def test_order_cancelled_handler_logs(caplog):
    handler = OrderCancelledHandler()
    event = OrderCancelled(aggregate_id=uuid4())

    with caplog.at_level(logging.INFO, logger="modules.orders.handlers"):
        handler.handle(event)

    assert any(
        "Processando cancelamento do pedido" in record.getMessage()
        for record in caplog.records
    )


def test_order_status_changed_handler_logs(caplog):
    handler = OrderStatusChangedHandler()
    event = OrderStatusChanged(aggregate_id=uuid4())

    with caplog.at_level(logging.INFO, logger="modules.orders.handlers"):
        handler.handle(event)

    assert any(
        "Processando mudança de status do pedido" in record.getMessage()
        for record in caplog.records
    )


def test_in_memory_event_bus_routes_events():
    bus = InMemoryEventBus()
    handled = []

    class CapturingHandler:
        def handle(self, event) -> None:
            handled.append(event)

    handler = CapturingHandler()
    event = OrderCreated(aggregate_id=uuid4())

    bus.subscribe(OrderCreated, handler)
    bus.publish(event)

    assert handled == [event]
