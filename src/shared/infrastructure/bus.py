"""In-memory event bus implementation."""

from __future__ import annotations

from typing import Dict, List, Type

from shared.domain.bus import IEventBus, IEventHandler
from shared.domain.events import DomainEvent


class InMemoryEventBus(IEventBus):
    """Simple in-process event bus."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[DomainEvent], List[IEventHandler]] = {}

    def subscribe(self, event_class: Type[DomainEvent], handler: IEventHandler) -> None:
        handlers = self._handlers.setdefault(event_class, [])
        if handler not in handlers:
            handlers.append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            handler.handle(event)


# Global bus instance (singleton)

event_bus = InMemoryEventBus()
