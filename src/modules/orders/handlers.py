"""Event handlers for Orders domain events."""

from __future__ import annotations

import structlog

from modules.orders.events import OrderCancelled, OrderCreated, OrderStatusChanged
from shared.domain.bus import IEventHandler

logger = structlog.get_logger(__name__)


class OrderCreatedHandler(IEventHandler[OrderCreated]):
    def handle(self, event: OrderCreated) -> None:
        logger.info(
            f"Processando evento de criação do pedido {event.aggregate_id}",
            order_id=str(event.aggregate_id),
        )


class OrderCancelledHandler(IEventHandler[OrderCancelled]):
    def handle(self, event: OrderCancelled) -> None:
        logger.info(
            f"Processando cancelamento do pedido {event.aggregate_id}",
            order_id=str(event.aggregate_id),
        )


class OrderStatusChangedHandler(IEventHandler[OrderStatusChanged]):
    def handle(self, event: OrderStatusChanged) -> None:
        logger.info(
            f"Processando mudança de status do pedido {event.aggregate_id}",
            order_id=str(event.aggregate_id),
        )


order_created_handler = OrderCreatedHandler()
order_cancelled_handler = OrderCancelledHandler()
order_status_changed_handler = OrderStatusChangedHandler()
