"""Domain events primitives for the modular monolith."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Base domain event (immutable)."""

    aggregate_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    occurred_on: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_name: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_name", self.__class__.__name__)


class DomainEventMixin:
    """Mixin for aggregate roots that collect domain events in memory."""

    _domain_events: list[DomainEvent]

    def add_domain_event(self, event: DomainEvent) -> None:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        if hasattr(self, "_domain_events"):
            self._domain_events.clear()

    @property
    def domain_events(self) -> list[DomainEvent]:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return list(self._domain_events)
