"""Customer DTOs for the Service Layer.

Framework-agnostic data transfer objects using Pydantic v2.
These are the contracts between the API layer (DRF Serializers)
and the Service layer.  DTOs are immutable (``frozen=True``).

- ``CreateCustomerDTO``: input for customer creation.
- ``CustomerOutputDTO``: output with masked document (RN-CLI-005).
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator
from validate_docbr import CNPJ, CPF

if TYPE_CHECKING:
    from modules.customers.models import Customer


# ---------------------------------------------------------------------------
# Enum (framework-agnostic — NOT Django TextChoices)
# ---------------------------------------------------------------------------


class DocumentTypeEnum(StrEnum):
    """CPF or CNPJ identifier type."""

    CPF = "CPF"
    CNPJ = "CNPJ"


# ---------------------------------------------------------------------------
# Input DTO
# ---------------------------------------------------------------------------


class CreateCustomerDTO(BaseModel):
    """Immutable DTO for customer creation requests.

    Validates:
    - ``document`` is sanitised (non-digits stripped) and checked via
      *validate-docbr*.
    - ``email`` is a well-formed address (Pydantic ``EmailStr``).
    - ``document_type`` must be CPF or CNPJ.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    document: str
    document_type: DocumentTypeEnum
    email: EmailStr
    phone: str = ""
    address: str = ""

    @field_validator("document", mode="before")
    @classmethod
    def sanitize_document(cls, v: str) -> str:
        """Strip non-digit characters (accept formatted or raw input)."""
        if not isinstance(v, str):
            return v
        return re.sub(r"\D", "", v)

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        """Cross-field validation: check CPF/CNPJ using *validate-docbr*."""
        if self.document_type == DocumentTypeEnum.CPF:
            validator = CPF()
        else:
            validator = CNPJ()

        if not validator.validate(self.document):
            raise ValueError(f"Invalid {self.document_type} number.")
        return self


# ---------------------------------------------------------------------------
# Output DTO
# ---------------------------------------------------------------------------


class UpdateCustomerDTO(BaseModel):
    """Immutable DTO for customer update requests.

    All fields are optional — only supplied fields will be updated.
    ``document`` and ``document_type`` are validated together when both
    are present.
    """

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Output DTO
# ---------------------------------------------------------------------------


class CustomerOutputDTO(BaseModel):
    """Immutable DTO for customer API responses.

    The ``document`` field is **masked** (``***1234``) to comply with
    RN-CLI-005 (sensitive data must not appear in responses/logs).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    document: str
    document_type: str
    email: str
    phone: str
    address: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def mask_document(raw_document: str) -> str:
        """Mask a document, showing only the last 4 digits."""
        suffix = raw_document[-4:] if raw_document else "????"
        return f"***{suffix}"

    @classmethod
    def from_entity(cls, customer: Customer) -> CustomerOutputDTO:
        """Build an output DTO from a Customer model instance."""
        return cls(
            id=customer.id,
            name=customer.name,
            document=cls.mask_document(customer.document),
            document_type=customer.document_type,
            email=customer.email,
            phone=customer.phone,
            address=customer.address,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
