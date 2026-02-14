"""Signals for automatic Order status history tracking."""

from __future__ import annotations

from typing import Optional, Protocol, cast

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from modules.orders.models import Order, OrderStatusHistory


class _OrderStatusAware(Protocol):
    _previous_status: str | None
    _status_change_notes: str | None


@receiver(pre_save, sender=Order)
def _capture_previous_status(sender, instance: Order, **kwargs) -> None:
    status_instance = cast(_OrderStatusAware, instance)
    if not instance.pk:
        status_instance._previous_status = None
        return
    previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )
    status_instance._previous_status = previous_status


@receiver(post_save, sender=Order)
def _create_status_history(sender, instance: Order, created: bool, **kwargs) -> None:
    status_instance = cast(_OrderStatusAware, instance)
    previous_status: Optional[str] = getattr(status_instance, "_previous_status", None)
    notes = getattr(status_instance, "_status_change_notes", None)

    should_create = created or previous_status != instance.status
    if not should_create:
        _clear_transient_status_attrs(instance)
        return

    if created and notes is None:
        notes = "Order created"
    if notes is None:
        notes = ""

    OrderStatusHistory.objects.create(
        order=instance,
        old_status=previous_status,
        new_status=instance.status,
        notes=notes,
    )

    _clear_transient_status_attrs(instance)


def _clear_transient_status_attrs(instance: Order) -> None:
    if hasattr(instance, "_previous_status"):
        delattr(instance, "_previous_status")
    if hasattr(instance, "_status_change_notes"):
        delattr(instance, "_status_change_notes")
