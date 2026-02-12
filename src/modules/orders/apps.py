from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.orders"
    label = "orders"

    def ready(self) -> None:
        from modules.orders.events import (
            OrderCancelled,
            OrderCreated,
            OrderStatusChanged,
        )
        from modules.orders.handlers import (
            order_cancelled_handler,
            order_created_handler,
            order_status_changed_handler,
        )
        from shared.infrastructure.bus import event_bus

        event_bus.subscribe(OrderCreated, order_created_handler)
        event_bus.subscribe(OrderCancelled, order_cancelled_handler)
        event_bus.subscribe(OrderStatusChanged, order_status_changed_handler)
