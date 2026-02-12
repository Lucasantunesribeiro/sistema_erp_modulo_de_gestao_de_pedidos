"""Order service layer (Use Cases).

Orchestrates the core business logic for order creation,
status management, and cancellation.  All write operations
are atomic — the service defines the unit-of-work boundary.

Business rules enforced:
- RN-CLI-003: Customer must be active.
- RN-PRO-002: Product must be active.
- RN-EST-001/002/003/004: Atomic stock reservation with SELECT FOR UPDATE.
- RN-EST-005/006: Atomic stock release on cancellation.
- RN-PED-001: Status transitions validated against state machine.
- RN-PED-002/003: History recorded on every status change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

import structlog

from django.db import transaction

from modules.orders.constants import OrderStatus
from modules.orders.events import OrderCancelled, OrderCreated, OrderStatusChanged
from modules.orders.exceptions import (
    CustomerNotFound,
    InactiveCustomer,
    InactiveProduct,
    InsufficientStock,
    InvalidOrderStatus,
    OrderNotFound,
    ProductNotFound,
)

if TYPE_CHECKING:
    from modules.customers.repositories.interfaces import ICustomerRepository
    from modules.orders.dtos import CreateOrderDTO
    from modules.orders.models import Order
    from modules.orders.repositories.interfaces import IOrderRepository
    from modules.products.repositories.interfaces import IProductRepository

logger = structlog.get_logger(__name__)


class OrderService:
    """Application service for Order use-cases.

    Receives repositories via constructor injection (DIP).
    """

    def __init__(
        self,
        order_repository: IOrderRepository,
        customer_repository: ICustomerRepository,
        product_repository: IProductRepository,
    ) -> None:
        self._order_repo = order_repository
        self._customer_repo = customer_repository
        self._product_repo = product_repository

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @transaction.atomic
    def create_order(self, dto: CreateOrderDTO) -> Order:
        """Create a new order with atomic stock reservation.

        Steps:
        1. Validate customer exists and is active.
        2. For each item (sorted by product PK to avoid deadlocks):
           - Lock product row (SELECT FOR UPDATE).
           - Validate product is active.
           - Validate sufficient stock.
           - Snapshot current price.
           - Deduct stock.
        3. Persist order + items atomically.
        4. Record initial status history.

        Raises:
            CustomerNotFound: customer does not exist.
            InactiveCustomer: customer is inactive (RN-CLI-003).
            ProductNotFound: a product does not exist.
            InactiveProduct: a product is inactive (RN-PRO-002).
            InsufficientStock: not enough stock (RN-EST-004).
        """
        log = logger.bind(customer_id=str(dto.customer_id))
        log.info("order.creation_started")

        # 0. Idempotency check
        if dto.idempotency_key:
            existing = self._order_repo.get_by_idempotency_key(dto.idempotency_key)
            if existing:
                log.info(
                    "order.idempotency_hit",
                    order_id=str(existing.id),
                    key=dto.idempotency_key,
                )
                return existing

        # 1. Validate customer
        customer = self._customer_repo.get_by_id(str(dto.customer_id))
        if not customer:
            raise CustomerNotFound(f"Customer {dto.customer_id} not found.")
        if not customer.is_active:
            raise InactiveCustomer(f"Customer {dto.customer_id} is inactive.")

        # 2. Process items — sort by product_id to prevent deadlocks
        from modules.products.models import Product

        sorted_items = sorted(dto.items, key=lambda i: str(i.product_id))
        repo_items = []

        for item_dto in sorted_items:
            product = (
                Product.objects.select_for_update()
                .filter(id=item_dto.product_id)
                .first()
            )
            if not product:
                raise ProductNotFound(f"Product {item_dto.product_id} not found.")
            if product.status != "active":
                raise InactiveProduct(f"Product {item_dto.product_id} is inactive.")
            if product.stock_quantity < item_dto.quantity:
                raise InsufficientStock(
                    f"Product {product.sku}: requested {item_dto.quantity}, "
                    f"available {product.stock_quantity}."
                )

            # Deduct stock
            product.stock_quantity -= item_dto.quantity
            product.save(update_fields=["stock_quantity", "updated_at"])

            log.info(
                "order.stock_reserved",
                product_id=str(product.id),
                quantity=item_dto.quantity,
                remaining=product.stock_quantity,
            )

            repo_items.append(
                {
                    "product_id": product.id,
                    "quantity": item_dto.quantity,
                    "unit_price": product.price,
                }
            )

        # 3. Persist order + items
        order = self._order_repo.create(
            {
                "customer_id": dto.customer_id,
                "items": repo_items,
                "notes": dto.notes or "",
                "idempotency_key": dto.idempotency_key,
            }
        )

        created_event = OrderCreated(aggregate_id=order.id)
        order.add_domain_event(created_event)
        self._order_repo.save(order)

        # 4. Record initial history
        self._order_repo.add_history(
            order_id=order.id,
            status=OrderStatus.PENDING,
            notes="Order created",
        )

        log.info("order.created", order_id=str(order.id))
        self._on_order_created(order)

        # Re-fetch with prefetch for output
        order_with_relations = self._order_repo.get_by_id(str(order.id))
        return order_with_relations or order

    @transaction.atomic
    def update_status(
        self,
        order_id: UUID,
        new_status: str,
        notes: str = "",
    ) -> Order:
        """Transition an order to a new status.

        Acquires a row-level lock (``SELECT FOR UPDATE``) on the order
        before validating the transition — prevents concurrent mutations.
        Uses ``Order.can_transition_to`` for FSM validation (RN-PED-001).
        Records history (RN-PED-002/003).

        Raises:
            OrderNotFound: order does not exist.
            InvalidOrderStatus: transition is not allowed.
        """
        order = self._order_repo.get_for_update(str(order_id))
        if not order:
            raise OrderNotFound(f"Order {order_id} not found.")

        log = logger.bind(
            order_id=str(order_id),
            current_status=order.status,
            new_status=new_status,
        )

        if not order.can_transition_to(new_status):
            log.warning("order.invalid_transition")
            raise InvalidOrderStatus(
                f"Cannot transition from {order.status} to {new_status}."
            )

        old_status = order.status
        order.status = new_status
        order.add_domain_event(OrderStatusChanged(aggregate_id=order.id))
        self._order_repo.save(order)

        self._order_repo.add_history(
            order_id=order.id,
            status=new_status,
            notes=notes,
            old_status=old_status,
        )

        log.info("order.status_updated")
        self._dispatch_status_event(order, old_status, new_status)
        return self._order_repo.get_by_id(str(order_id))

    @transaction.atomic
    def cancel_order(self, order_id: UUID, notes: str = "") -> Order:
        """Cancel an order and release reserved stock (RN-EST-005/006).

        Acquires a row-level lock on the order **first** to prevent
        concurrent cancellations from releasing stock twice.

        Raises:
            OrderNotFound: order does not exist.
            InvalidOrderStatus: cancellation not allowed from current status.
        """
        # 1. Lock the order row
        order = self._order_repo.get_for_update(str(order_id))
        if not order:
            raise OrderNotFound(f"Order {order_id} not found.")

        log = logger.bind(order_id=str(order_id), current_status=order.status)

        # 2. Validate FSM transition
        if not order.can_transition_to(OrderStatus.CANCELLED):
            log.warning("order.cancel_not_allowed")
            raise InvalidOrderStatus(f"Cannot cancel order in status {order.status}.")

        # 3. Release stock — lock products sorted by PK to prevent deadlocks
        from modules.products.models import Product

        items = list(order.items.all().order_by("product_id"))
        for item in items:
            product = (
                Product.objects.select_for_update().filter(id=item.product_id).first()
            )
            if product:
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity", "updated_at"])
                log.info(
                    "order.stock_released",
                    product_id=str(product.id),
                    quantity=item.quantity,
                    restored_stock=product.stock_quantity,
                )

        # 4. Update status on the already-locked row
        old_status = order.status
        order.status = OrderStatus.CANCELLED
        order.add_domain_event(OrderCancelled(aggregate_id=order.id))
        self._order_repo.save(order)

        # 5. Record history
        self._order_repo.add_history(
            order_id=order.id,
            status=OrderStatus.CANCELLED,
            notes=notes or "Order cancelled",
            old_status=old_status,
        )

        log.info("order.cancelled")
        self._on_order_cancelled(order)
        return self._order_repo.get_by_id(str(order_id))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> Order:
        """Retrieve a single order by ID.

        Raises:
            OrderNotFound: if the order does not exist.
        """
        order = self._order_repo.get_by_id(order_id)
        if not order:
            raise OrderNotFound(f"Order {order_id} not found.")
        return order

    def list_orders(self, filters: Optional[Dict[str, Any]] = None) -> List[Order]:
        """Return a list of orders, optionally filtered."""
        return self._order_repo.list(filters)

    # ------------------------------------------------------------------
    # Domain Event Hooks (Phase 6 — Outbox Pattern)
    # ------------------------------------------------------------------

    def _on_order_created(self, order: Order) -> None:
        """Hook: fired after an order is successfully created.

        Will publish ``OrderCreated`` + ``StockReserved`` events once
        the Outbox pattern is implemented (Phase 6).
        """
        logger.info("order.event.created", order_id=str(order.id))

    def _on_order_cancelled(self, order: Order) -> None:
        """Hook: fired after an order is cancelled.

        Will publish ``OrderCancelled`` + ``StockReleased`` events once
        the Outbox pattern is implemented (Phase 6).
        """
        logger.info("order.event.cancelled", order_id=str(order.id))

    def _dispatch_status_event(
        self, order: Order, old_status: str, new_status: str
    ) -> None:
        """Hook: fired after any status transition.

        Will publish ``OrderStatusChanged`` event once the Outbox
        pattern is implemented (Phase 6).
        """
        logger.info(
            "order.event.status_changed",
            order_id=str(order.id),
            old_status=old_status,
            new_status=new_status,
        )
