"""Product domain exceptions.

Raised by the Service Layer when business rules are violated.
The API layer (Views) catches these and translates them into
appropriate HTTP responses.
"""

from __future__ import annotations


class ProductAlreadyExists(Exception):
    """A product with the same SKU already exists.

    Covers RN-PRO-001 (unique SKU).
    """


class ProductNotFound(Exception):
    """The requested product does not exist or has been soft-deleted."""
