"""Base abstract models for the ERP system.

Provides:
- ``BaseModel``: UUIDv7 primary key + created_at / updated_at timestamps.
- ``SoftDeleteModel``: Extends BaseModel with soft-delete via ``deleted_at``.

Design decisions (validated by backend-architect):
- Single ``deleted_at`` field instead of dual ``is_deleted`` + ``deleted_at``
  (single source of truth, avoids inconsistency).
- ``objects`` manager returns ALL records (unfiltered).  Use ``.alive()``
  explicitly to exclude soft-deleted rows — prevents silent data loss.
- ``delete()`` returns Django-compatible ``(count, {label: count})`` tuple.
- ``save()`` guard ensures ``updated_at`` is included when ``update_fields``
  is specified (Django skips ``auto_now`` fields otherwise).
"""

from __future__ import annotations

import uuid6

from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# BaseModel
# ---------------------------------------------------------------------------


class BaseModel(models.Model):
    """Abstract base with UUIDv7 PK and timestamp bookkeeping."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid6.uuid7,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        """Ensure ``updated_at`` is refreshed even when ``update_fields`` is passed."""
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "updated_at" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["updated_at"]
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Soft Delete infrastructure
# ---------------------------------------------------------------------------


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet with soft-delete helpers."""

    def alive(self) -> SoftDeleteQuerySet:
        """Return only non-deleted records."""
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> SoftDeleteQuerySet:
        """Return only soft-deleted records."""
        return self.filter(deleted_at__isnull=False)

    def delete(self) -> tuple[int, dict[str, int]]:
        """Bulk soft-delete: sets ``deleted_at`` + ``updated_at``."""
        now = timezone.now()
        count = self.alive().update(deleted_at=now, updated_at=now)
        return count, {self.model._meta.label: count}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Permanently remove all records in the queryset."""
        return super().delete()


class SoftDeleteManager(models.Manager):
    """Manager that exposes ``.alive()`` / ``.dead()`` on the queryset."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)

    def alive(self) -> SoftDeleteQuerySet:
        return self.get_queryset().alive()

    def dead(self) -> SoftDeleteQuerySet:
        return self.get_queryset().dead()


class SoftDeleteModel(BaseModel):
    """Abstract model with soft-delete via a single ``deleted_at`` timestamp.

    - ``objects`` is **unfiltered** (returns all rows).
    - Use ``Model.objects.alive()`` to exclude soft-deleted rows.
    - ``delete()`` performs a soft-delete; ``hard_delete()`` removes physically.
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
    )

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        """Computed: ``True`` when the record has been soft-deleted."""
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False) -> tuple[int, dict[str, int]]:
        """Soft-delete this instance (no-op if already deleted)."""
        if self.is_deleted:
            return 0, {}
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    def hard_delete(self, using=None, keep_parents=False) -> tuple[int, dict[str, int]]:
        """Permanently remove this record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> None:
        """Restore a soft-deleted record. No-op if already alive."""
        if not self.is_deleted:
            return
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
