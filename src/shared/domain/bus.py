"""Domain bus interfaces for in-process event handling."""

from __future__ import annotations

from typing import Generic, Protocol, Type, TypeVar

from shared.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent, contravariant=True)


class IEventHandler(Protocol, Generic[E]):
    """Handler interface for domain events."""

    def handle(self, event: E) -> None: ...


class IEventBus(Protocol):
    """Event bus interface."""

    def publish(self, event: DomainEvent) -> None: ...

    def subscribe(self, event_class: Type[E], handler: IEventHandler[E]) -> None: ...
