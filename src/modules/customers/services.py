"""Customer service layer (Use Cases).

Orchestrates business logic for the Customer aggregate, delegating
persistence to the injected ``ICustomerRepository``.

Business rules enforced here:
- RN-CLI-001: CPF/CNPJ must be unique.
- RN-CLI-002: Email must be unique.
- RN-CLI-004: Soft delete via repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog
from django.db import transaction

from modules.customers.exceptions import CustomerAlreadyExists, CustomerNotFound
from modules.customers.models import Customer

if TYPE_CHECKING:
    from modules.customers.dtos import CreateCustomerDTO, UpdateCustomerDTO
    from modules.customers.repositories.interfaces import ICustomerRepository

logger = structlog.get_logger(__name__)


class CustomerService:
    """Application service for Customer use-cases.

    Receives an ``ICustomerRepository`` via constructor injection (DIP).
    """

    def __init__(self, repository: ICustomerRepository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @transaction.atomic
    def create_customer(self, dto: CreateCustomerDTO) -> Customer:
        """Create a new customer after enforcing uniqueness rules.

        Raises:
            CustomerAlreadyExists: if document (RN-CLI-001) or
                email (RN-CLI-002) is already taken.
        """
        log = logger.bind(document_type=dto.document_type, email=dto.email)

        if self._repo.get_by_document(dto.document):
            log.warning("customer.duplicate_document")
            raise CustomerAlreadyExists(
                f"Document {dto.document_type} already registered."
            )

        if self._repo.get_by_email(dto.email):
            log.warning("customer.duplicate_email")
            raise CustomerAlreadyExists("Email already registered.")

        customer = Customer(
            name=dto.name,
            document=dto.document,
            document_type=dto.document_type,
            email=dto.email,
            phone=dto.phone,
            address=dto.address,
        )
        customer = self._repo.save(customer)
        log.info("customer.created", customer_id=str(customer.id))
        return customer

    @transaction.atomic
    def update_customer(self, id: str, dto: UpdateCustomerDTO) -> Customer:
        """Update an existing customer with the supplied fields.

        Raises:
            CustomerNotFound: if the customer does not exist.
            CustomerAlreadyExists: if the new email collides (RN-CLI-002).
        """
        customer = self._repo.get_by_id(id)
        if not customer:
            raise CustomerNotFound(f"Customer {id} not found.")

        log = logger.bind(customer_id=str(id))

        if dto.email is not None and dto.email != customer.email:
            existing = self._repo.get_by_email(dto.email)
            if existing:
                log.warning("customer.duplicate_email")
                raise CustomerAlreadyExists("Email already registered.")

        for field in ("name", "email", "phone", "address", "is_active"):
            value = getattr(dto, field)
            if value is not None:
                setattr(customer, field, value)

        customer = self._repo.save(customer)
        log.info("customer.updated")
        return customer

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_customers(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Customer]:
        """Return a list of customers, optionally filtered."""
        return self._repo.list(filters)

    def get_customer(self, id: str) -> Customer:
        """Retrieve a single customer by ID.

        Raises:
            CustomerNotFound: if the customer does not exist.
        """
        customer = self._repo.get_by_id(id)
        if not customer:
            raise CustomerNotFound(f"Customer {id} not found.")
        logger.info("customer.retrieved", customer_id=str(id))
        return customer

    @transaction.atomic
    def delete_customer(self, id: str) -> None:
        """Soft-delete a customer (RN-CLI-004).

        Raises:
            CustomerNotFound: if the customer does not exist.
        """
        customer = self._repo.get_by_id(id)
        if not customer:
            raise CustomerNotFound(f"Customer {id} not found.")
        self._repo.delete(id)
        logger.info("customer.soft_deleted", customer_id=str(id))
