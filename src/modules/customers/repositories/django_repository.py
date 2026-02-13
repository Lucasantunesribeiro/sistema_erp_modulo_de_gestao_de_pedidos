"""Django ORM implementation of the Customer repository.

Satisfies ``ICustomerRepository`` using Django's QuerySet API.
Error handling follows the Null Object pattern: methods return ``None``
instead of raising HTTP-level exceptions — the Service Layer decides
how to translate a missing entity into an API response.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from django.core.exceptions import ValidationError
from django.db import transaction

from modules.customers.models import Customer
from modules.customers.repositories.interfaces import ICustomerRepository

logger = structlog.get_logger(__name__)


class CustomerDjangoRepository(ICustomerRepository):
    """Concrete Customer repository backed by Django ORM."""

    def get_by_id(self, id: str) -> Optional[Customer]:
        """Retrieve a customer by primary key.

        Returns ``None`` for non-existent or invalid IDs (e.g. malformed UUID).
        """
        try:
            return Customer.objects.filter(id=id).first()
        except (ValueError, ValidationError):
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Customer]:
        """List customers with optional Django ORM look-ups.

        Examples of valid filters::

            {"is_active": True}
            {"name__icontains": "acme", "is_active": True}
        """
        queryset = Customer.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return list(queryset)

    @transaction.atomic
    def save(self, entity: Customer) -> Customer:
        """Persist (create or update) a customer."""
        entity.save()
        logger.info(
            "customer.saved",
            customer_id=str(entity.id),
            is_new=entity._state.adding,
        )
        return entity

    @transaction.atomic
    def delete(self, id: str) -> bool:
        """Soft-delete a customer by ID.

        Returns ``True`` if the customer was found and soft-deleted,
        ``False`` if no customer exists with the given ID.
        """
        customer = self.get_by_id(id)
        if not customer:
            return False
        customer.delete()
        logger.info("customer.soft_deleted", customer_id=str(id))
        return True

    def get_by_document(self, document: str) -> Optional[Customer]:
        """Retrieve a customer by CPF/CNPJ (digits only)."""
        return Customer.objects.filter(document=document).first()

    def get_by_email(self, email: str) -> Optional[Customer]:
        """Retrieve a customer by email address."""
        return Customer.objects.filter(email=email).first()
