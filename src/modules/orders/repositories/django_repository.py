"""Django ORM implementation of the Order repository.

Satisfies ``IOrderRepository`` using Django's QuerySet API.
All write operations are wrapped in ``transaction.atomic()`` to ensure
the Order aggregate (Order + OrderItems) is persisted atomically.

Concurrency control on status updates uses ``select_for_update()``
to prevent race conditions (no ``version`` field exists on the model).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from django.core.exceptions import ValidationError
from django.db import transaction

from modules.core.models import OutboxEvent
from modules.orders.constants import OrderStatus
from modules.orders.models import Order, OrderItem, OrderStatusHistory
from modules.orders.repositories.interfaces import IOrderRepository

logger = structlog.get_logger(__name__)


class OrderDjangoRepository(IOrderRepository):
    """Concrete Order repository backed by Django ORM."""

    # ------------------------------------------------------------------
    # Create (aggregate root + children)
    # ------------------------------------------------------------------

    @transaction.atomic
    def create(self, data: Dict[str, Any]) -> Order:
        """Create an order with its items atomically.

        ``data`` keys:
        - ``customer_id`` (required)
        - ``items`` (required): list of dicts with ``product_id``,
          ``quantity``, ``unit_price``
        - ``idempotency_key`` (optional)
        - ``notes`` (optional)
        """
        order = Order(
            customer_id=data["customer_id"],
            idempotency_key=data.get("idempotency_key"),
            notes=data.get("notes", ""),
        )
        order.save()

        total = Decimal("0.00")
        items = data.get("items", [])
        for item_data in items:
            item = OrderItem(
                order=order,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
            )
            item.save()
            total += item.subtotal

        order.total_amount = total
        order.save(update_fields=["total_amount", "updated_at"])

        log = logger.bind(order_id=str(order.id), item_count=len(items))
        log.info("order.created")

        return order

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @transaction.atomic
    def update(self, id: UUID, data: Dict[str, Any]) -> Order:
        """Update order fields using ``select_for_update`` for safety."""
        order = Order.objects.select_for_update().filter(id=id).first()
        if not order:
            raise Order.DoesNotExist(f"Order {id} not found.")

        for field, value in data.items():
            if value is not None:
                setattr(order, field, value)

        order.save()
        logger.info("order.updated", order_id=str(id))
        return order

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, id: str) -> Optional[Order]:
        """Retrieve an order with eager-loaded relations.

        Uses ``select_related`` for the customer FK (single JOIN) and
        ``prefetch_related`` for items, items→product, and status
        history (separate batched queries).  Prevents N+1.

        Returns ``None`` for non-existent or invalid IDs.
        """
        try:
            return (
                Order.objects.select_related("customer")
                .prefetch_related("items__product", "status_history")
                .filter(id=id)
                .first()
            )
        except (ValueError, ValidationError):
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Order]:
        """List orders with optional filters and eager-loaded relations.

        Supported filter keys:
        - ``status``
        - ``customer_id``
        - ``created_at__range``
        """
        queryset = Order.objects.select_related("customer").prefetch_related(
            "items__product", "status_history"
        )
        if filters:
            queryset = queryset.filter(**filters)
        return list(queryset)

    # ------------------------------------------------------------------
    # Save / Delete (IRepository contract)
    # ------------------------------------------------------------------

    @transaction.atomic
    def save(self, entity: Order) -> Order:
        """Persist (create or update) an order."""
        entity.save()

        events = entity.domain_events if hasattr(entity, "domain_events") else []
        for event in events:
            payload = _serialize_event_payload(event)
            OutboxEvent.objects.create(
                event_type=event.event_name,
                aggregate_id=str(event.aggregate_id),
                payload=payload,
                topic="orders",
            )
        if hasattr(entity, "clear_domain_events"):
            entity.clear_domain_events()

        logger.info("order.saved", order_id=str(entity.id), event_count=len(events))
        return entity

    @transaction.atomic
    def delete(self, id: str) -> bool:
        """Soft-delete an order by ID."""
        order = self.get_by_id(id)
        if not order:
            return False
        order.delete()
        logger.info("order.soft_deleted", order_id=str(id))
        return True

    # ------------------------------------------------------------------
    # Order-specific queries
    # ------------------------------------------------------------------

    @transaction.atomic
    def add_history(
        self,
        order_id: UUID,
        status: OrderStatus,
        notes: str = "",
        old_status: Optional[str] = None,
    ) -> OrderStatusHistory:
        """Record a status change in the order's audit trail."""
        if old_status is None:
            order = Order.objects.filter(id=order_id).first()
            old_status = order.status if order else None

        history = OrderStatusHistory(
            order_id=order_id,
            old_status=old_status,
            new_status=status,
            notes=notes,
        )
        history.save()

        logger.info(
            "order.history_added",
            order_id=str(order_id),
            old_status=old_status,
            new_status=status,
        )
        return history

    def get_for_update(self, id: str) -> Optional[Order]:
        """Retrieve an order with a row-level lock (SELECT FOR UPDATE).

        Eager-loads items (with product) so the caller can iterate
        over them while the row is locked.  Returns ``None`` for
        non-existent or invalid IDs.
        """
        try:
            return (
                Order.objects.select_for_update()
                .select_related("customer")
                .prefetch_related("items__product", "status_history")
                .filter(id=id)
                .first()
            )
        except (ValueError, ValidationError):
            return None

    def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        """Retrieve an order by its idempotency key."""
        return (
            Order.objects.select_related("customer")
            .prefetch_related("items__product", "status_history")
            .filter(idempotency_key=key)
            .first()
        )


def _serialize_event_payload(event: Any) -> Dict[str, Any]:
    data = asdict(event)
    normalized = _normalize_for_json(data)
    return json.loads(json.dumps(normalized))


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_for_json(val) for key, val in value.items()}
    return value
