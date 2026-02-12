"""Domain events for the Orders bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from shared.domain.events import DomainEvent


@dataclass(frozen=True)
class OrderCreated(DomainEvent):
    """Raised when an order is created."""


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    """Raised when an order is cancelled."""


@dataclass(frozen=True)
class OrderStatusChanged(DomainEvent):
    """Raised when an order status changes."""
