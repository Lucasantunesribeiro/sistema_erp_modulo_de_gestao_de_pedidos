"""Customer repository interface.

Extends ``IRepository[Customer]`` with look-ups required by
business rules RN-CLI-001 (unique CPF/CNPJ) and RN-CLI-002 (unique email).
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from modules.core.repositories.interfaces import IRepository

if TYPE_CHECKING:
    from modules.customers.models import Customer


class ICustomerRepository(IRepository["Customer"]):
    """Repository contract for the Customer aggregate."""

    @abstractmethod
    def get_by_document(self, document: str) -> Optional[Customer]:
        """Retrieve a customer by CPF/CNPJ."""

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Customer]:
        """Retrieve a customer by email address."""
