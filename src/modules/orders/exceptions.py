"""Order domain exceptions.

Raised by the Service Layer when business rules are violated.
The API layer (Views) catches these and translates them into
appropriate HTTP responses.
"""

from __future__ import annotations


class OrderNotFound(Exception):
    """The requested order does not exist or has been soft-deleted."""


class InvalidOrderStatus(Exception):
    """An invalid status transition was attempted (RN-PED-001)."""


class InsufficientStock(Exception):
    """Not enough stock to fulfil the order (RN-EST-004)."""


class InactiveCustomer(Exception):
    """The customer is inactive and cannot place orders (RN-CLI-003)."""


class CustomerNotFound(Exception):
    """The customer referenced by the order does not exist."""


class ProductNotFound(Exception):
    """A product referenced by an order item does not exist."""


class InactiveProduct(Exception):
    """A product referenced by an order item is inactive (RN-PRO-002)."""
