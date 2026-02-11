"""Customer domain exceptions.

Raised by the Service Layer when business rules are violated.
The API layer (Views) catches these and translates them into
appropriate HTTP responses.
"""

from __future__ import annotations


class CustomerAlreadyExists(Exception):
    """A customer with the same document or email already exists.

    Covers RN-CLI-001 (unique CPF/CNPJ) and RN-CLI-002 (unique email).
    """


class CustomerNotFound(Exception):
    """The requested customer does not exist or has been soft-deleted."""
