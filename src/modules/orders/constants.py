"""Order domain constants.

Defines status choices and valid status transitions for the order
state machine (see BUSINESS_RULES.md section 3.2).
"""

from django.db import models


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    CONFIRMED = "CONFIRMED", "Confirmado"
    SEPARATED = "SEPARATED", "Separado"
    SHIPPED = "SHIPPED", "Enviado"
    DELIVERED = "DELIVERED", "Entregue"
    CANCELLED = "CANCELLED", "Cancelado"


VALID_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.SEPARATED, OrderStatus.CANCELLED},
    OrderStatus.SEPARATED: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

TERMINAL_STATES: set[str] = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}

ORDER_NUMBER_MAX_RETRIES = 5
