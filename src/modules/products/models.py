"""Product model with SKU uniqueness and stock control.

Business rules implemented:
- RN-PRO-001: SKU must be unique in the system.
- RN-PRO-002: Inactive product cannot be sold (enforced at service layer).
- RN-PRO-003: Price must be greater than zero.
- RN-PRO-004: Stock quantity cannot be negative.
- RN-PRO-005: Soft delete via ``deleted_at`` (inherited from SoftDeleteModel).
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from modules.core.models import SoftDeleteModel

logger = structlog.get_logger(__name__)


class ProductStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class Product(SoftDeleteModel):
    """Product aggregate root.

    ``sku`` is normalised to uppercase on save to prevent visual duplicates
    (e.g. "sku-01" vs "SKU-01").  ``unique=True`` on ``sku`` creates a
    UNIQUE INDEX in MySQL — no additional index is needed.
    """

    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.ACTIVE,
    )

    class Meta:
        db_table = "products"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"], name="products_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0),
                name="products_price_positive",
            ),
        ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        super().clean()
        if self.sku:
            self.sku = self.sku.strip().upper()
        if self.price is not None and self.price <= 0:
            raise ValidationError({"price": "Price must be greater than zero."})
        if self.stock_quantity is not None and self.stock_quantity < 0:
            raise ValidationError(
                {"stock_quantity": "Stock quantity cannot be negative."}
            )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs) -> None:
        is_new = self._state.adding
        if self.sku:
            self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)
        if is_new:
            logger.info(
                "product_created",
                product_id=str(self.id),
                sku=self.sku,
                name=self.name,
            )

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"
