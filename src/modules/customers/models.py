"""Customer model with CPF/CNPJ validation and soft delete.

Business rules implemented:
- RN-CLI-001: CPF/CNPJ must be unique in the system.
- RN-CLI-002: Email must be unique in the system.
- RN-CLI-003: Inactive customer cannot place orders (enforced at service layer).
- RN-CLI-004: Soft delete via ``deleted_at`` (inherited from SoftDeleteModel).
- RN-CLI-005: Sensitive data (CPF/CNPJ) masked in ``__str__`` and logs.
"""

from __future__ import annotations

import re

import structlog
from validate_docbr import CNPJ, CPF

from django.core.exceptions import ValidationError
from django.db import models

from modules.core.models import SoftDeleteModel

logger = structlog.get_logger(__name__)


class DocumentType(models.TextChoices):
    CPF = "CPF", "CPF"
    CNPJ = "CNPJ", "CNPJ"


class Customer(SoftDeleteModel):
    """Customer aggregate root.

    ``document`` stores only digits (sanitised on save).
    ``unique=True`` on ``document`` and ``email`` enforces global uniqueness
    regardless of soft-delete state — a government-issued identifier should
    never be reused.  Use ``restore()`` to reactivate a soft-deleted customer.
    """

    name = models.CharField(max_length=255)
    document = models.CharField(max_length=14, unique=True)
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    email = models.EmailField(max_length=254, unique=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "customers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="customers_created_idx"),
            models.Index(fields=["is_active"], name="customers_active_idx"),
        ]

    # ------------------------------------------------------------------
    # Sanitisation
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_document(value: str) -> str:
        """Strip all non-digit characters from a document string."""
        return re.sub(r"\D", "", value)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        super().clean()
        if self.document:
            self.document = self._sanitize_document(self.document)
        self._validate_document()

    def _validate_document(self) -> None:
        """Validate CPF or CNPJ using *validate-docbr*."""
        if self.document_type == DocumentType.CPF:
            validator = CPF()
        elif self.document_type == DocumentType.CNPJ:
            validator = CNPJ()
        else:
            raise ValidationError({"document_type": "Invalid document type."})

        if not validator.validate(self.document):
            logger.warning(
                "customer.invalid_document",
                document_type=self.document_type,
                document_suffix=self.document[-4:] if self.document else "",
            )
            raise ValidationError({"document": f"Invalid {self.document_type} number."})

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs) -> None:
        if self.document:
            self.document = self._sanitize_document(self.document)
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Display (RN-CLI-005 — mask sensitive data)
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        suffix = self.document[-4:] if self.document else "????"
        return f"{self.name} ({self.document_type}: ***{suffix})"
