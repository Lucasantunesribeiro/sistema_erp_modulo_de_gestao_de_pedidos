"""Order repository interface.

Extends ``IRepository[Order]`` with methods required by the Order
aggregate — atomic creation with items, status history tracking,
and idempotency-key look-up.

The Service Layer depends exclusively on this contract (DIP).
The concrete Django ORM implementation will be provided in Stage 27.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from modules.core.repositories.interfaces import IRepository

if TYPE_CHECKING:
    from modules.orders.constants import OrderStatus
    from modules.orders.models import Order, OrderStatusHistory


class IOrderRepository(IRepository["Order"]):
    """Repository contract for the Order aggregate root.

    The Order aggregate includes OrderItem children and
    OrderStatusHistory records.  Mutations must be atomic.
    """

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Order:
        """Create an order with its items atomically.

        ``data`` must include ``customer_id``, ``items`` (list of dicts
        with ``product_id``, ``quantity``, ``unit_price``), and optionally
        ``idempotency_key`` and ``notes``.
        """

    @abstractmethod
    def update(self, id: UUID, data: Dict[str, Any]) -> Order:
        """Update order fields (e.g. status, notes, total_amount)."""

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[Order]:
        """Retrieve an order with prefetched items and status history."""

    @abstractmethod
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Order]:
        """List orders with optional filters."""

    @abstractmethod
    def add_history(
        self,
        order_id: UUID,
        status: OrderStatus,
        notes: str = "",
    ) -> OrderStatusHistory:
        """Record a status change in the order's audit trail."""

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        """Retrieve an order by its idempotency key."""
