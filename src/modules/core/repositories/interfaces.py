"""Generic repository interface (Dependency Inversion Principle).

Provides ``IRepository[T]``, the base abstract class that all
domain-specific repository interfaces extend.  Service-layer code
depends on this abstraction, never on Django ORM directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, Protocol, TypeVar

from django.db import models

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Queryable(Protocol[T_co]):
    def filter(self, **kwargs: Any) -> models.QuerySet: ...


class IRepository(ABC, Generic[T]):
    """Base generic repository contract.

    Type parameter ``T`` represents the domain entity managed by the
    repository (e.g. ``Customer``, ``Product``).
    """

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]:
        """Retrieve an entity by its primary key."""

    @abstractmethod
    def list(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Queryable[T]:
        """List entities with optional filters."""

    @abstractmethod
    def save(self, entity: T) -> T:
        """Persist (create or update) an entity."""

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Remove an entity by ID (soft or hard delete)."""
