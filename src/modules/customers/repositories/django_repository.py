"""Django ORM implementation of the Customer repository."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction

from modules.customers.models import Customer
from modules.customers.repositories.interfaces import ICustomerRepository


class CustomerDjangoRepository(ICustomerRepository):
    """Concrete Customer repository backed by Django ORM."""

    def get_by_id(self, id: str) -> Optional[Customer]:
        """Retrieve a customer by ID (UUID)."""
        try:
            return Customer.objects.filter(id=id).first()
        except Exception:
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Customer]:
        """List customers with optional filters."""
        queryset = Customer.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return list(queryset)

    @transaction.atomic
    def save(self, entity: Customer) -> Customer:
        """Persist (create or update) a customer."""
        entity.save()
        return entity

    @transaction.atomic
    def delete(self, id: str) -> bool:
        """Soft-delete a customer by ID."""
        customer = self.get_by_id(id)
        if not customer:
            return False
        customer.delete()
        return True

    def get_by_document(self, document: str) -> Optional[Customer]:
        """Retrieve a customer by CPF/CNPJ."""
        return Customer.objects.filter(document=document).first()

    def get_by_email(self, email: str) -> Optional[Customer]:
        """Retrieve a customer by email address."""
        return Customer.objects.filter(email=email).first()
